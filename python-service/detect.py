from __future__ import annotations

"""
Fast plot detection pipeline — targets < 20s on a 400-plot site plan.

Two strategies only (fast ones):
  1. Connected components on thresholded binary  — auto-tunes gap-close size
  2. Canny + morphological close                 — single best config

Deduplication uses center-distance NMS (no per-pixel mask ops → 100× faster
than IoU on large images).

A /debug endpoint lets you visualise every intermediate step in a browser.
"""

import base64
import cv2
import numpy as np
from typing import List, Dict, Any, Tuple, Optional

from ocr import extract_plot_number

MAX_PROCESS_DIM = 2500   # keep small — 2500px is plenty for detection + OCR


# ─────────────────────────────────────────────────────────────────────────────
#  Image loading
# ─────────────────────────────────────────────────────────────────────────────

def load_image(image_bytes: bytes) -> np.ndarray:
    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("Could not decode image. Use JPG or PNG.")
    h, w = img.shape[:2]
    longest = max(h, w)
    if longest > MAX_PROCESS_DIM:
        scale = MAX_PROCESS_DIM / longest
        img = cv2.resize(img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
    return img


# ─────────────────────────────────────────────────────────────────────────────
#  Preprocessing
# ─────────────────────────────────────────────────────────────────────────────

def to_enhanced_gray(img: np.ndarray) -> np.ndarray:
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    return clahe.apply(gray)


def build_line_mask(enhanced: np.ndarray) -> np.ndarray:
    """
    Four-strategy union: catches thin, faint, dark, and lightly-printed lines.
    Returns binary where lines = 255.
    """
    h, w = enhanced.shape[:2]
    block = max(11, (min(h, w) // 60) | 1)  # must be odd

    adap_g = cv2.adaptiveThreshold(enhanced, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, block, 6)
    adap_m = cv2.adaptiveThreshold(enhanced, 255,
        cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY_INV, block, 8)
    _, otsu = cv2.threshold(enhanced, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    _, fixed = cv2.threshold(enhanced, 180, 255, cv2.THRESH_BINARY_INV)

    out = cv2.bitwise_or(adap_g, adap_m)
    out = cv2.bitwise_or(out, otsu)
    out = cv2.bitwise_or(out, fixed)
    return out


# ─────────────────────────────────────────────────────────────────────────────
#  Fast deduplication — center-distance NMS
# ─────────────────────────────────────────────────────────────────────────────

def bbox_of(points: List[Dict], h: int, w: int) -> Tuple[int, int, int, int]:
    xs = [p["x"] * w for p in points]
    ys = [p["y"] * h for p in points]
    return int(min(xs)), int(min(ys)), int(max(xs)), int(max(ys))


def boxes_overlap(a: Tuple, b: Tuple, threshold: float = 0.4) -> bool:
    """Fast axis-aligned bounding-box IoU."""
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    ix1 = max(ax1, bx1); iy1 = max(ay1, by1)
    ix2 = min(ax2, bx2); iy2 = min(ay2, by2)
    iw = max(0, ix2 - ix1); ih = max(0, iy2 - iy1)
    inter = iw * ih
    if inter == 0:
        return False
    area_a = (ax2 - ax1) * (ay2 - ay1)
    area_b = (bx2 - bx1) * (by2 - by1)
    union = area_a + area_b - inter
    return (inter / union) > threshold if union > 0 else False


def deduplicate(candidates: List[Dict], h: int, w: int) -> List[Dict]:
    kept: List[Dict] = []
    kept_boxes: List[Tuple] = []
    for cand in sorted(candidates, key=lambda c: c["confidence"], reverse=True):
        box = bbox_of(cand["points"], h, w)
        if not any(boxes_overlap(box, kb) for kb in kept_boxes):
            kept.append(cand)
            kept_boxes.append(box)
    return kept


# ─────────────────────────────────────────────────────────────────────────────
#  Contour → dict
# ─────────────────────────────────────────────────────────────────────────────

def contour_to_plot(contour, img_h: int, img_w: int, label: str,
                    min_ratio: float = 0.0002) -> Optional[Dict]:
    area = cv2.contourArea(contour)
    total = img_h * img_w
    if area < total * min_ratio or area > total * 0.15:
        return None
    epsilon = 0.015 * cv2.arcLength(contour, True)
    approx = cv2.approxPolyDP(contour, epsilon, True)
    sides = len(approx)
    if sides < 3 or sides > 30:
        return None
    points = [{"x": round(float(p[0][0]) / img_w, 4),
               "y": round(float(p[0][1]) / img_h, 4)} for p in approx]
    return {
        "id": label, "points": points,
        "plot_number": None, "number_detected": False,
        "confidence": 0.62 if sides == 4 else 0.42,
        "sides": sides,
        "area_ratio": round(area / total, 6),
        "_area_px": int(area),
    }


# ─────────────────────────────────────────────────────────────────────────────
#  Method 1: Connected components — auto-tune gap size
# ─────────────────────────────────────────────────────────────────────────────

def cc_pass(enhanced: np.ndarray, img: np.ndarray, gap_px: int) -> List[Dict]:
    h, w = enhanced.shape[:2]
    line_mask = build_line_mask(enhanced)

    k = np.ones((gap_px, gap_px), np.uint8)
    thick = cv2.dilate(line_mask, k, iterations=2)
    not_lines = cv2.bitwise_not(thick)

    # Remove speckle noise
    open_k = max(2, gap_px // 3)
    k_open = np.ones((open_k, open_k), np.uint8)
    cleaned = cv2.morphologyEx(not_lines, cv2.MORPH_OPEN, k_open)

    num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(cleaned, connectivity=8)
    total = h * w
    results = []

    for lid in range(1, num_labels):
        area = int(stats[lid, cv2.CC_STAT_AREA])
        if area < total * 0.0002 or area > total * 0.15:
            continue
        mask = np.zeros((h, w), np.uint8)
        mask[labels == lid] = 255
        contours_f, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours_f:
            continue
        c = max(contours_f, key=cv2.contourArea)
        r = contour_to_plot(c, h, w, f"cc{gap_px}_{lid}")
        if r:
            results.append(r)

    return results


def method_connected_components(img: np.ndarray, enhanced: np.ndarray) -> List[Dict]:
    """Try gap sizes 3→5→7→10→14 px, keep the run that yields the most valid plots."""
    best: List[Dict] = []
    for gap in [3, 5, 7, 10, 14]:
        results = cc_pass(enhanced, img, gap)
        if len(results) > len(best):
            best = results
        if len(results) >= 20:
            break          # good enough — stop early
    return best


# ─────────────────────────────────────────────────────────────────────────────
#  Method 2: Canny + morphological close
# ─────────────────────────────────────────────────────────────────────────────

def method_canny(img: np.ndarray, enhanced: np.ndarray) -> List[Dict]:
    h, w = enhanced.shape[:2]
    results = []

    for (lo, hi, blur, close_k) in [
        (30, 100, 1, 5),
        (50, 150, 3, 7),
    ]:
        blurred = cv2.GaussianBlur(enhanced, (blur * 2 + 1, blur * 2 + 1), 0) if blur > 1 else enhanced
        edges = cv2.Canny(blurred, lo, hi)
        k = np.ones((close_k, close_k), np.uint8)
        closed = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, k, iterations=2)
        contours, _ = cv2.findContours(closed, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
        for i, c in enumerate(contours):
            r = contour_to_plot(c, h, w, f"canny{lo}_{close_k}_{i}")
            if r:
                results.append(r)

    return results


# ─────────────────────────────────────────────────────────────────────────────
#  OCR — 3 quick variants per region
# ─────────────────────────────────────────────────────────────────────────────

def crop_region(img: np.ndarray, points: List[Dict]) -> np.ndarray:
    h, w = img.shape[:2]
    xs = [int(p["x"] * w) for p in points]
    ys = [int(p["y"] * h) for p in points]
    x1 = max(0, min(xs) - 8); y1 = max(0, min(ys) - 8)
    x2 = min(w, max(xs) + 8); y2 = min(h, max(ys) + 8)
    return img[y1:y2, x1:x2]


def run_ocr(img: np.ndarray, points: List[Dict]) -> Tuple[Optional[str], float]:
    region = crop_region(img, points)
    if region.size == 0:
        return None, 0.0
    gray = cv2.cvtColor(region, cv2.COLOR_BGR2GRAY) if len(region.shape) == 3 else region
    k_sharp = np.array([[-1,-1,-1],[-1,9,-1],[-1,-1,-1]])
    for variant in [gray, cv2.filter2D(gray, -1, k_sharp), cv2.bitwise_not(gray)]:
        result, conf = extract_plot_number(variant)
        if result:
            return result, conf
    return None, 0.0


# ─────────────────────────────────────────────────────────────────────────────
#  Public API
# ─────────────────────────────────────────────────────────────────────────────

def detect_plots(image_bytes: bytes) -> List[Dict[str, Any]]:
    img = load_image(image_bytes)
    h, w = img.shape[:2]
    enhanced = to_enhanced_gray(img)

    # Collect candidates from both methods
    candidates: List[Dict] = []
    candidates.extend(method_connected_components(img, enhanced))
    candidates.extend(method_canny(img, enhanced))

    if not candidates:
        return []

    # Fast bbox-NMS dedup
    unique = deduplicate(candidates, h, w)

    # OCR each surviving plot
    final: List[Dict[str, Any]] = []
    for idx, cand in enumerate(unique):
        plot_num, _ = run_ocr(img, cand["points"])
        has_num = plot_num is not None
        is_rect = cand["sides"] == 4
        conf = 0.92 if (is_rect and has_num) else (
               0.82 if has_num else (
               0.62 if is_rect else 0.42))
        final.append({
            "id": f"plot_{idx}",
            "points": cand["points"],
            "plot_number": plot_num,
            "number_detected": has_num,
            "confidence": conf,
            "sides": cand["sides"],
            "area_ratio": cand["area_ratio"],
        })

    final.sort(key=lambda x: x["confidence"], reverse=True)
    return final


# ─────────────────────────────────────────────────────────────────────────────
#  Debug helper — step-by-step base64 images
# ─────────────────────────────────────────────────────────────────────────────

def debug_pipeline(image_bytes: bytes) -> Dict[str, Any]:
    img = load_image(image_bytes)
    h, w = img.shape[:2]
    enhanced = to_enhanced_gray(img)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    line_mask = build_line_mask(enhanced)

    # Show gap=7 as representative intermediate
    k = np.ones((7, 7), np.uint8)
    thick = cv2.dilate(line_mask, k, iterations=2)
    not_lines = cv2.bitwise_not(thick)

    def b64(arr: np.ndarray) -> str:
        _, buf = cv2.imencode(".png", arr)
        return base64.b64encode(buf).decode()

    # Annotated result
    plots = detect_plots(image_bytes)
    annotated = img.copy()
    for p in plots:
        pts = np.array([[int(pt["x"]*w), int(pt["y"]*h)] for pt in p["points"]], np.int32)
        cv2.polylines(annotated, [pts], True, (0, 220, 60), 2)
        cx = int(sum(pt["x"] for pt in p["points"]) / len(p["points"]) * w)
        cy = int(sum(pt["y"] for pt in p["points"]) / len(p["points"]) * h)
        lbl = p["plot_number"] or "?"
        cv2.putText(annotated, lbl, (cx-10, cy+5),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.35, (0, 0, 255), 1)

    return {
        "original":    b64(img),
        "grayscale":   b64(gray),
        "enhanced":    b64(enhanced),
        "line_mask":   b64(line_mask),
        "thick_lines": b64(thick),
        "plot_areas":  b64(not_lines),
        "annotated":   b64(annotated),
        "total_detected": len(plots),
    }
