from __future__ import annotations

"""
Ultimate plot detection — three strategies + auto-tuning + Hough line fallback.

If a pass returns < MIN_EXPECTED_PLOTS, it auto-increases gap-close strength
and retries until it hits a pass that yields a plausible count.
"""

import base64
import cv2
import numpy as np
from typing import List, Dict, Any, Tuple, Optional

from ocr import extract_plot_number

MAX_PROCESS_DIM = 4500
MIN_EXPECTED_PLOTS = 10     # below this → auto-retry with stronger gap close


# ─────────────────────────────────────────────────────────────────────────────
#  Utilities
# ─────────────────────────────────────────────────────────────────────────────

def ensure_max_resolution(img: np.ndarray) -> Tuple[np.ndarray, float]:
    h, w = img.shape[:2]
    longest = max(h, w)
    if longest <= MAX_PROCESS_DIM:
        return img, 1.0
    scale = MAX_PROCESS_DIM / longest
    out = cv2.resize(img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
    return out, scale


def polygon_iou(pts_a: List[Dict], pts_b: List[Dict], h: int, w: int) -> float:
    def to_cv(pts):
        return np.array([[int(p["x"] * w), int(p["y"] * h)] for p in pts], dtype=np.int32)
    m_a = np.zeros((h, w), np.uint8)
    m_b = np.zeros((h, w), np.uint8)
    cv2.fillPoly(m_a, [to_cv(pts_a)], 255)
    cv2.fillPoly(m_b, [to_cv(pts_b)], 255)
    inter = cv2.bitwise_and(m_a, m_b)
    union = cv2.bitwise_or(m_a, m_b)
    u = int(np.count_nonzero(union))
    return int(np.count_nonzero(inter)) / u if u else 0.0


def deduplicate_iou(candidates: List[Dict], h: int, w: int, threshold: float = 0.35) -> List[Dict]:
    kept: List[Dict] = []
    for cand in sorted(candidates, key=lambda c: c["confidence"], reverse=True):
        if not any(polygon_iou(cand["points"], k["points"], h, w) > threshold for k in kept):
            kept.append(cand)
    return kept


def contour_to_result(contour, img_h: int, img_w: int, label: str,
                      min_area_ratio: float = 0.0002) -> Optional[Dict]:
    area = cv2.contourArea(contour)
    total = img_h * img_w
    if area < total * min_area_ratio or area > total * 0.15:
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


def crop_region(img: np.ndarray, points: List[Dict]) -> np.ndarray:
    h, w = img.shape[:2]
    xs = [int(p["x"] * w) for p in points]
    ys = [int(p["y"] * h) for p in points]
    x1 = max(0, min(xs) - 8)
    y1 = max(0, min(ys) - 8)
    x2 = min(w, max(xs) + 8)
    y2 = min(h, max(ys) + 8)
    return img[y1:y2, x1:x2]


# ─────────────────────────────────────────────────────────────────────────────
#  Preprocessing
# ─────────────────────────────────────────────────────────────────────────────

def enhance_gray(gray: np.ndarray) -> np.ndarray:
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    return clahe.apply(gray)


def build_line_mask(enhanced: np.ndarray) -> np.ndarray:
    """
    Binary mask: boundary LINES = white.
    Tries 4 strategies and ORs them — catches thin, faint, and thick lines.
    """
    h, w = enhanced.shape[:2]
    block = max(11, (min(h, w) // 80) | 1)

    # 1. Adaptive Gaussian
    adap_gauss = cv2.adaptiveThreshold(enhanced, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, block, 6)
    # 2. Adaptive Mean
    adap_mean = cv2.adaptiveThreshold(enhanced, 255,
        cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY_INV, block, 8)
    # 3. Otsu
    _, otsu = cv2.threshold(enhanced, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    # 4. Fixed threshold at 180 (catches lightly-printed lines)
    _, fixed = cv2.threshold(enhanced, 180, 255, cv2.THRESH_BINARY_INV)

    combined = cv2.bitwise_or(adap_gauss, adap_mean)
    combined = cv2.bitwise_or(combined, otsu)
    combined = cv2.bitwise_or(combined, fixed)
    return combined


def thicken_lines(line_mask: np.ndarray, gap_px: int) -> np.ndarray:
    """Dilate line mask to close gaps of up to gap_px pixels."""
    k = max(3, gap_px)
    kernel = np.ones((k, k), np.uint8)
    return cv2.dilate(line_mask, kernel, iterations=2)


# ─────────────────────────────────────────────────────────────────────────────
#  Method 1: Connected components — auto-tuned gap closing
# ─────────────────────────────────────────────────────────────────────────────

def method_cc_gap(img: np.ndarray, gray: np.ndarray, gap_px: int) -> List[Dict]:
    h, w = img.shape[:2]
    enhanced = enhance_gray(gray)
    line_mask = build_line_mask(enhanced)
    thick = thicken_lines(line_mask, gap_px)
    not_lines = cv2.bitwise_not(thick)

    open_k = max(3, gap_px // 4)
    k_open = np.ones((open_k, open_k), np.uint8)
    plot_mask = cv2.morphologyEx(not_lines, cv2.MORPH_OPEN, k_open, iterations=1)

    num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(plot_mask, connectivity=8)
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
        r = contour_to_result(c, h, w, f"cc_{gap_px}_{lid}")
        if r:
            results.append(r)

    return results


def method_connected_components(img: np.ndarray, gray: np.ndarray) -> List[Dict]:
    """Auto-tune gap-close kernel: try 3 → 6 → 9 → 12 → 18 px until ≥ MIN_EXPECTED_PLOTS."""
    best: List[Dict] = []
    for gap in [3, 5, 7, 10, 14, 20]:
        results = method_cc_gap(img, gray, gap)
        if len(results) > len(best):
            best = results
        if len(results) >= MIN_EXPECTED_PLOTS:
            break
    return best


# ─────────────────────────────────────────────────────────────────────────────
#  Method 2: Canny + morphological close
# ─────────────────────────────────────────────────────────────────────────────

def method_canny_filled(img: np.ndarray, gray: np.ndarray) -> List[Dict]:
    h, w = img.shape[:2]
    results = []
    enhanced = enhance_gray(gray)

    for (lo, hi, blur) in [(20, 80, 1), (40, 120, 3), (60, 180, 5)]:
        blurred = cv2.GaussianBlur(enhanced, (blur * 2 + 1, blur * 2 + 1), 0) if blur > 1 else enhanced
        edges = cv2.Canny(blurred, lo, hi)

        for close_k in [3, 5, 8]:
            kernel = np.ones((close_k, close_k), np.uint8)
            closed = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel, iterations=2)
            contours, _ = cv2.findContours(closed, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
            for i, contour in enumerate(contours):
                r = contour_to_result(contour, h, w, f"canny_{lo}_{close_k}_{i}")
                if r:
                    results.append(r)

    return results


# ─────────────────────────────────────────────────────────────────────────────
#  Method 3: Hough lines → draw on canvas → find enclosed regions
#  Best for clean CAD/rectangular grid layouts
# ─────────────────────────────────────────────────────────────────────────────

def method_hough(img: np.ndarray, gray: np.ndarray) -> List[Dict]:
    h, w = img.shape[:2]
    enhanced = enhance_gray(gray)
    blurred = cv2.GaussianBlur(enhanced, (3, 3), 0)
    edges = cv2.Canny(blurred, 50, 150)

    min_len = min(h, w) // 25   # at least 4% of shorter side
    lines = cv2.HoughLinesP(edges, rho=1, theta=np.pi / 180,
                             threshold=40, minLineLength=min_len, maxLineGap=8)
    if lines is None:
        return []

    canvas = np.zeros((h, w), np.uint8)
    for line in lines:
        x1, y1, x2, y2 = line[0]
        cv2.line(canvas, (x1, y1), (x2, y2), 255, 2)

    kernel = np.ones((5, 5), np.uint8)
    closed = cv2.morphologyEx(canvas, cv2.MORPH_CLOSE, kernel, iterations=2)
    not_lines = cv2.bitwise_not(closed)

    k_open = np.ones((3, 3), np.uint8)
    cleaned = cv2.morphologyEx(not_lines, cv2.MORPH_OPEN, k_open, iterations=1)

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
        r = contour_to_result(c, h, w, f"hough_{lid}")
        if r:
            results.append(r)

    return results


# ─────────────────────────────────────────────────────────────────────────────
#  Method 4: Watershed segmentation
# ─────────────────────────────────────────────────────────────────────────────

def method_watershed(img: np.ndarray, gray: np.ndarray) -> List[Dict]:
    h, w = img.shape[:2]
    enhanced = enhance_gray(gray)
    _, thresh = cv2.threshold(enhanced, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    bg_k = max(3, min(h, w) // 200)
    sure_bg = cv2.dilate(thresh, np.ones((bg_k, bg_k), np.uint8), iterations=3)
    dist = cv2.distanceTransform(thresh, cv2.DIST_L2, 5)
    _, sure_fg = cv2.threshold(dist, 0.3 * dist.max(), 255, 0)
    sure_fg = np.uint8(sure_fg)
    unknown = cv2.subtract(sure_bg, sure_fg)

    _, markers = cv2.connectedComponents(sure_fg)
    markers += 1
    markers[unknown == 255] = 0

    img_color = img.copy()
    cv2.watershed(img_color, markers)

    total = h * w
    results = []
    for lbl in np.unique(markers):
        if lbl <= 1:
            continue
        mask = np.zeros((h, w), np.uint8)
        mask[markers == lbl] = 255
        contours_f, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours_f:
            continue
        c = max(contours_f, key=cv2.contourArea)
        r = contour_to_result(c, h, w, f"ws_{lbl}")
        if r:
            results.append(r)

    return results


# ─────────────────────────────────────────────────────────────────────────────
#  Multi-config OCR
# ─────────────────────────────────────────────────────────────────────────────

def run_best_ocr(img: np.ndarray, points: List[Dict]) -> Tuple[Optional[str], float]:
    region = crop_region(img, points)
    if region.size == 0:
        return None, 0.0

    gray = cv2.cvtColor(region, cv2.COLOR_BGR2GRAY) if len(region.shape) == 3 else region

    sharp_k = np.array([[-1,-1,-1],[-1,9,-1],[-1,-1,-1]])
    sharp = cv2.filter2D(gray, -1, sharp_k)
    inv = cv2.bitwise_not(gray)

    for variant in [gray, sharp, inv]:
        result, conf = extract_plot_number(variant)
        if result:
            return result, conf

    return None, 0.0


# ─────────────────────────────────────────────────────────────────────────────
#  Public API: detect_plots
# ─────────────────────────────────────────────────────────────────────────────

def detect_plots(image_bytes: bytes) -> List[Dict[str, Any]]:
    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("Could not decode image — ensure it is a valid JPG or PNG")

    img, _ = ensure_max_resolution(img)
    h, w = img.shape[:2]
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # ── All 4 methods ─────────────────────────────────────────────────────────
    all_candidates: List[Dict] = []
    all_candidates.extend(method_connected_components(img, gray))
    all_candidates.extend(method_canny_filled(img, gray))
    all_candidates.extend(method_hough(img, gray))
    all_candidates.extend(method_watershed(img, gray))

    if not all_candidates:
        return []

    # ── Deduplicate ───────────────────────────────────────────────────────────
    unique = deduplicate_iou(all_candidates, h, w, threshold=0.35)

    # ── OCR ───────────────────────────────────────────────────────────────────
    final: List[Dict[str, Any]] = []
    for idx, cand in enumerate(unique):
        plot_num, _ = run_best_ocr(img, cand["points"])
        has_num = plot_num is not None
        is_rect = cand["sides"] == 4
        conf = 0.92 if (is_rect and has_num) else (0.82 if has_num else (0.62 if is_rect else 0.42))
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
#  Debug helper — returns base64 intermediate images
# ─────────────────────────────────────────────────────────────────────────────

def debug_pipeline(image_bytes: bytes) -> Dict[str, str]:
    """Returns base64-encoded PNG images of each processing step."""
    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    img, _ = ensure_max_resolution(img)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    enhanced = enhance_gray(gray)
    line_mask = build_line_mask(enhanced)

    gap_px = max(3, min(img.shape[:2]) // 300)
    thick = thicken_lines(line_mask, gap_px)
    not_lines = cv2.bitwise_not(thick)

    def to_b64(arr: np.ndarray) -> str:
        _, buf = cv2.imencode(".png", arr)
        return base64.b64encode(buf).decode()

    # Annotated: draw detected plot borders
    annotated = img.copy()
    plots = detect_plots(image_bytes)
    h, w = img.shape[:2]
    for p in plots:
        pts = np.array([[int(pt["x"]*w), int(pt["y"]*h)] for pt in p["points"]], np.int32)
        cv2.polylines(annotated, [pts], True, (0, 255, 0), 2)
        cx = int(sum(pt["x"] for pt in p["points"]) / len(p["points"]) * w)
        cy = int(sum(pt["y"] for pt in p["points"]) / len(p["points"]) * h)
        label = p["plot_number"] or "?"
        cv2.putText(annotated, label, (cx-10, cy+5), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0,0,255), 1)

    return {
        "original":   to_b64(img),
        "grayscale":  to_b64(gray),
        "enhanced":   to_b64(enhanced),
        "line_mask":  to_b64(line_mask),
        "thick_lines":to_b64(thick),
        "plot_areas": to_b64(not_lines),
        "annotated":  to_b64(annotated),
        "total_detected": str(len(plots)),
    }
