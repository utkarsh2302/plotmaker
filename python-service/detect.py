from __future__ import annotations

import cv2
import numpy as np
from typing import List, Dict, Any, Tuple

from ocr import extract_plot_number

MAX_PROCESS_DIM = 4500


def ensure_max_resolution(img: np.ndarray) -> Tuple[np.ndarray, float]:
    h, w = img.shape[:2]
    longest = max(h, w)
    if longest <= MAX_PROCESS_DIM:
        return img, 1.0
    scale = MAX_PROCESS_DIM / longest
    resized = cv2.resize(img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
    return resized, scale


def _build_line_mask(gray: np.ndarray) -> np.ndarray:
    """
    Return a binary mask where boundary LINES are white (255).
    Combines adaptive threshold + Otsu to be robust across different scan types.
    """
    h, w = gray.shape[:2]

    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(gray)

    # Adaptive threshold — good for scanned / uneven-lit drawings
    block = max(11, (min(h, w) // 80) | 1)   # odd, ~1.25% of shorter side
    adaptive = cv2.adaptiveThreshold(
        enhanced, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV,
        blockSize=block, C=6
    )

    # Otsu — good for clean CAD exports
    _, otsu = cv2.threshold(enhanced, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

    # Union gives us the best of both
    return cv2.bitwise_or(adaptive, otsu)


def detect_plots(image_bytes: bytes) -> List[Dict[str, Any]]:
    """
    Detects plot polygons in a site plan image.

    Core idea: boundary lines are dark → threshold to find them → dilate to
    close gaps → invert to get the enclosed plot areas → connected components
    to label each individual plot.

    This is far more reliable than contour-on-edges for dense 200-400 plot layouts.
    """
    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("Could not decode image — ensure it is a valid JPG or PNG")

    img, _ = ensure_max_resolution(img)
    h, w = img.shape[:2]
    total_area = h * w

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # --- Step 1: isolate boundary lines ---
    line_mask = _build_line_mask(gray)

    # Dilate lines to close small gaps between segments
    # Kernel size scales with image: ~0.3% of shorter side, min 3px
    gap_k = max(3, min(h, w) // 300)
    gap_kernel = np.ones((gap_k, gap_k), np.uint8)
    thick_lines = cv2.dilate(line_mask, gap_kernel, iterations=2)

    # --- Step 2: plot areas = everything that is NOT a line ---
    not_lines = cv2.bitwise_not(thick_lines)

    # Remove tiny specks (noise inside plots)
    open_k = max(3, min(h, w) // 600)
    open_kernel = np.ones((open_k, open_k), np.uint8)
    plot_mask = cv2.morphologyEx(not_lines, cv2.MORPH_OPEN, open_kernel, iterations=1)

    # --- Step 3: connected components = individual plots ---
    num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(
        plot_mask, connectivity=8
    )

    # Area range: each plot should be 0.02% – 15% of total image area.
    # For 400 plots: avg = 0.25%, so 0.02% min still catches small corner plots.
    min_area = total_area * 0.0002   # 0.02%
    max_area = total_area * 0.15     # 15%

    results: List[Dict[str, Any]] = []

    for label_id in range(1, num_labels):   # 0 = background
        area = int(stats[label_id, cv2.CC_STAT_AREA])
        if area < min_area or area > max_area:
            continue

        # Build single-component mask and find its polygon
        comp_mask = np.zeros((h, w), np.uint8)
        comp_mask[labels == label_id] = 255

        contours_found, _ = cv2.findContours(
            comp_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )
        if not contours_found:
            continue

        contour = max(contours_found, key=cv2.contourArea)

        # Polygon approximation — 1.5% of arc length is tighter than before,
        # preserves plot shape better
        epsilon = 0.015 * cv2.arcLength(contour, True)
        approx = cv2.approxPolyDP(contour, epsilon, True)
        sides = len(approx)

        if sides < 3 or sides > 30:
            continue

        points = [
            {"x": round(float(pt[0][0]) / w, 4), "y": round(float(pt[0][1]) / h, 4)}
            for pt in approx
        ]

        # Bounding box for OCR crop
        x = int(stats[label_id, cv2.CC_STAT_LEFT])
        y_s = int(stats[label_id, cv2.CC_STAT_TOP])
        bw = int(stats[label_id, cv2.CC_STAT_WIDTH])
        bh = int(stats[label_id, cv2.CC_STAT_HEIGHT])

        pad = max(4, min(bw, bh) // 8)
        x1 = max(0, x - pad)
        y1 = max(0, y_s - pad)
        x2 = min(w, x + bw + pad)
        y2 = min(h, y_s + bh + pad)
        region = img[y1:y2, x1:x2]

        plot_number, _ = extract_plot_number(region)
        has_number = plot_number is not None
        is_rect = sides == 4

        if is_rect and has_number:
            confidence = 0.90
        elif has_number:
            confidence = 0.80
        elif is_rect:
            confidence = 0.60
        else:
            confidence = 0.40

        results.append({
            "id": f"detected_{label_id}",
            "points": points,
            "plot_number": plot_number,
            "number_detected": has_number,
            "confidence": round(confidence, 2),
            "sides": sides,
            "area_ratio": round(area / total_area, 6),
        })

    results.sort(key=lambda x: x["confidence"], reverse=True)
    return results
