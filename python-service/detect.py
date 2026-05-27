import cv2
import numpy as np
from ocr import extract_plot_number

MAX_PROCESS_DIM = 4500  # px — cap before any OpenCV work


def ensure_max_resolution(img: np.ndarray) -> tuple[np.ndarray, float]:
    """
    Downscale image to MAX_PROCESS_DIM on its longest side if necessary.
    Returns (scaled_img, scale_factor) where scale_factor = new / original.
    """
    h, w = img.shape[:2]
    longest = max(h, w)
    if longest <= MAX_PROCESS_DIM:
        return img, 1.0

    scale = MAX_PROCESS_DIM / longest
    new_w = int(w * scale)
    new_h = int(h * scale)
    resized = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_AREA)
    return resized, scale


def detect_plots(image_bytes: bytes) -> list[dict]:
    """
    Main detection pipeline.
    Takes raw image bytes, returns list of detected plot dicts with normalized (0-1) coordinates.
    """
    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    if img is None:
        raise ValueError("Could not decode image — ensure it is a valid JPG or PNG")

    # Safety cap: large images (300-500MB) get downscaled here
    img, _scale = ensure_max_resolution(img)

    h, w = img.shape[:2]
    total_area = h * w

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # CLAHE contrast enhancement
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(gray)

    # Canny edges
    edges = cv2.Canny(enhanced, threshold1=50, threshold2=150)

    # Dilate to close small gaps in plot boundaries
    kernel = np.ones((3, 3), np.uint8)
    dilated = cv2.dilate(edges, kernel, iterations=1)

    contours, _ = cv2.findContours(dilated, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

    results = []
    seen_centers = []

    for i, contour in enumerate(contours):
        area = cv2.contourArea(contour)

        # Filter by area: 0.1% to 20% of image
        if area < total_area * 0.001 or area > total_area * 0.20:
            continue

        # Approximate polygon
        epsilon = 0.02 * cv2.arcLength(contour, True)
        approx = cv2.approxPolyDP(contour, epsilon, True)
        sides = len(approx)

        # Keep 3-12 sided shapes
        if sides < 3 or sides > 12:
            continue

        # Normalize points to 0-1 (coordinates are already in the scaled image space,
        # and since we normalize by current w/h, they map correctly to the original)
        points = [
            {"x": round(float(pt[0][0]) / w, 4), "y": round(float(pt[0][1]) / h, 4)}
            for pt in approx
        ]

        # Deduplicate by center proximity
        cx = sum(p["x"] for p in points) / len(points)
        cy = sum(p["y"] for p in points) / len(points)
        too_close = any(abs(cx - sc[0]) < 0.02 and abs(cy - sc[1]) < 0.02 for sc in seen_centers)
        if too_close:
            continue
        seen_centers.append((cx, cy))

        # Crop region for OCR
        x, y, bw, bh = cv2.boundingRect(contour)
        pad = 4
        x1 = max(0, x - pad)
        y1 = max(0, y - pad)
        x2 = min(w, x + bw + pad)
        y2 = min(h, y + bh + pad)
        region = img[y1:y2, x1:x2]

        plot_number, _ = extract_plot_number(region)

        is_rect = sides == 4
        has_number = plot_number is not None

        if is_rect and has_number:
            confidence = 0.90
        elif has_number:
            confidence = 0.80
        elif is_rect:
            confidence = 0.60
        else:
            confidence = 0.40

        results.append({
            "id": f"detected_{i}",
            "points": points,
            "plot_number": plot_number,
            "number_detected": has_number,
            "confidence": round(confidence, 2),
            "sides": sides,
            "area_ratio": round(area / total_area, 4),
        })

    results.sort(key=lambda x: x["confidence"], reverse=True)
    return results
