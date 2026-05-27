from __future__ import annotations

"""
Dual-mode plot detection — color-independent for 3D renders.

MODE A — 3D render / photorealistic (auto-detected by saturation stats)
  Strategy: bilateral-smooth → Canny → close → find enclosed regions →
            filter out organic blobs by rectangularity score.
  Color-independent: works for orange, beige, yellow, blue — any plot color.
  Organic shapes (trees, shrubs) are rejected because they score low on
  rectangularity even when they have the same area as plots.

MODE B — 2D CAD drawing / flat technical plan
  Strategy: threshold boundary lines → connected components on inverted mask.
"""

import base64
import cv2
import numpy as np
from typing import List, Dict, Any, Tuple, Optional

from ocr import extract_plot_number

MAX_PROCESS_DIM = 2500
MIN_RECT_SCORE = 0.50   # below this → organic shape, not a plot


# ─────────────────────────────────────────────────────────────────────────────
#  Load / resize
# ─────────────────────────────────────────────────────────────────────────────

def load_image(image_bytes: bytes) -> np.ndarray:
    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("Could not decode image. Use JPG or PNG.")
    h, w = img.shape[:2]
    if max(h, w) > MAX_PROCESS_DIM:
        scale = MAX_PROCESS_DIM / max(h, w)
        img = cv2.resize(img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
    return img


# ─────────────────────────────────────────────────────────────────────────────
#  Image type detection
# ─────────────────────────────────────────────────────────────────────────────

def is_photorealistic(img: np.ndarray) -> bool:
    """High mean saturation = 3D render / photo. Low = 2D line drawing."""
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    return float(np.mean(hsv[:, :, 1])) > 35.0


# ─────────────────────────────────────────────────────────────────────────────
#  Shared helpers
# ─────────────────────────────────────────────────────────────────────────────

def rectangularity(contour) -> float:
    """How rectangular is this shape? 1.0 = perfect rectangle."""
    area = cv2.contourArea(contour)
    if area == 0:
        return 0.0
    rw, rh = cv2.minAreaRect(contour)[1]
    rect_area = rw * rh
    return area / rect_area if rect_area > 0 else 0.0


def aspect_ratio_ok(contour) -> bool:
    """Reject very elongated shapes (roads) and near-squares that are too thin."""
    _, (rw, rh), _ = cv2.minAreaRect(contour)
    if min(rw, rh) == 0:
        return False
    ratio = max(rw, rh) / min(rw, rh)
    return ratio < 8.0   # plots are usually not more than 8:1


def is_mostly_green(img: np.ndarray, contour, img_h: int, img_w: int) -> bool:
    """True if the region interior is dominated by dark green (trees / grass)."""
    mask = np.zeros((img_h, img_w), np.uint8)
    cv2.drawContours(mask, [contour], -1, 255, -1)
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    green_lo = np.array([35, 40, 30])
    green_hi = np.array([90, 255, 200])
    green_px = cv2.inRange(hsv, green_lo, green_hi)
    region_px = int(np.count_nonzero(mask))
    if region_px == 0:
        return False
    green_frac = int(np.count_nonzero(cv2.bitwise_and(green_px, green_px, mask=mask))) / region_px
    return green_frac > 0.55


def contour_to_plot(contour, img_h: int, img_w: int, label: str,
                    min_ratio: float = 0.0002) -> Optional[Dict]:
    area = cv2.contourArea(contour)
    total = img_h * img_w
    if area < total * min_ratio or area > total * 0.12:
        return None
    epsilon = 0.02 * cv2.arcLength(contour, True)
    approx = cv2.approxPolyDP(contour, epsilon, True)
    sides = len(approx)
    if sides < 3 or sides > 30:
        return None
    points = [{"x": round(float(p[0][0]) / img_w, 4),
               "y": round(float(p[0][1]) / img_h, 4)} for p in approx]
    return {
        "id": label, "points": points,
        "plot_number": None, "number_detected": False,
        "confidence": 0.65 if sides == 4 else 0.45,
        "sides": sides,
        "area_ratio": round(area / total, 6),
    }


def bbox_overlap(a: Tuple, b: Tuple, thr: float = 0.35) -> bool:
    ax1,ay1,ax2,ay2 = a;  bx1,by1,bx2,by2 = b
    ix = max(0, min(ax2,bx2) - max(ax1,bx1))
    iy = max(0, min(ay2,by2) - max(ay1,by1))
    inter = ix * iy
    if inter == 0:
        return False
    ua = (ax2-ax1)*(ay2-ay1) + (bx2-bx1)*(by2-by1) - inter
    return (inter/ua) > thr if ua > 0 else False


def bbox_of(pts: List[Dict], h: int, w: int) -> Tuple[int,int,int,int]:
    xs = [p["x"]*w for p in pts]; ys = [p["y"]*h for p in pts]
    return int(min(xs)), int(min(ys)), int(max(xs)), int(max(ys))


def deduplicate(candidates: List[Dict], h: int, w: int) -> List[Dict]:
    kept: List[Dict] = []; boxes: List[Tuple] = []
    for c in sorted(candidates, key=lambda x: x["confidence"], reverse=True):
        b = bbox_of(c["points"], h, w)
        if not any(bbox_overlap(b, kb) for kb in boxes):
            kept.append(c); boxes.append(b)
    return kept


def crop_region(img: np.ndarray, pts: List[Dict]) -> np.ndarray:
    h, w = img.shape[:2]
    xs=[int(p["x"]*w) for p in pts]; ys=[int(p["y"]*h) for p in pts]
    return img[max(0,min(ys)-8):min(h,max(ys)+8),
               max(0,min(xs)-8):min(w,max(xs)+8)]


def run_ocr(img: np.ndarray, pts: List[Dict]) -> Tuple[Optional[str], float]:
    region = crop_region(img, pts)
    if region.size == 0:
        return None, 0.0
    gray = cv2.cvtColor(region, cv2.COLOR_BGR2GRAY) if len(region.shape)==3 else region
    k = np.array([[-1,-1,-1],[-1,9,-1],[-1,-1,-1]])
    for v in [gray, cv2.filter2D(gray,-1,k), cv2.bitwise_not(gray)]:
        r, c = extract_plot_number(v)
        if r:
            return r, c
    return None, 0.0


# ─────────────────────────────────────────────────────────────────────────────
#  MODE A — 3D render detection (color-independent)
# ─────────────────────────────────────────────────────────────────────────────

def detect_photo_mode(img: np.ndarray) -> List[Dict]:
    """
    Works on any plot color. Key idea:
    1. Bilateral filter removes texture from trees while keeping hard plot edges.
    2. Canny finds the strong boundary edges.
    3. Morphological close seals the plot polygons.
    4. Connected components → candidates.
    5. Rectangularity + green-exclusion filters remove trees and roads.
    """
    h, w = img.shape[:2]
    total = h * w
    results: List[Dict] = []

    # ── Pass 1: bilateral-smoothed Canny ──────────────────────────────────
    # Bilateral removes tree texture but keeps sharp plot edges
    smooth = cv2.bilateralFilter(img, d=9, sigmaColor=75, sigmaSpace=75)
    gray_s = cv2.cvtColor(smooth, cv2.COLOR_BGR2GRAY)

    for (lo, hi, close_k) in [(30, 90, 7), (50, 130, 9), (20, 70, 11)]:
        edges = cv2.Canny(gray_s, lo, hi)
        k = np.ones((close_k, close_k), np.uint8)
        closed = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, k, iterations=2)
        not_edges = cv2.bitwise_not(closed)
        k_open = np.ones((5, 5), np.uint8)
        cleaned = cv2.morphologyEx(not_edges, cv2.MORPH_OPEN, k_open)

        num_l, labels, stats, _ = cv2.connectedComponentsWithStats(cleaned, connectivity=8)
        for lid in range(1, num_l):
            area = int(stats[lid, cv2.CC_STAT_AREA])
            if area < total * 0.0003 or area > total * 0.12:
                continue
            mask = np.zeros((h, w), np.uint8)
            mask[labels == lid] = 255
            cf, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if not cf:
                continue
            c = max(cf, key=cv2.contourArea)
            rect_score = rectangularity(c)
            if rect_score < MIN_RECT_SCORE:
                continue
            if not aspect_ratio_ok(c):
                continue
            if is_mostly_green(img, c, h, w):
                continue
            r = contour_to_plot(c, h, w, f"photo_{lo}_{lid}", min_ratio=0.0003)
            if r:
                r["confidence"] = min(0.92, 0.55 + rect_score * 0.4)
                results.append(r)

    # ── Pass 2: color-quantised uniform regions ───────────────────────────
    # Quantize to 12 colors → each plot becomes a solid single color →
    # easy to segment regardless of what that color actually is.
    small = cv2.resize(img, (min(w, 800), min(h, int(h * 800/w))), interpolation=cv2.INTER_AREA)
    data = small.reshape((-1, 3)).astype(np.float32)
    k_colors = 12
    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 1.0)
    _, labels_km, centers = cv2.kmeans(data, k_colors, None, criteria,
                                        5, cv2.KMEANS_RANDOM_CENTERS)
    quantized_small = centers[labels_km.flatten()].reshape(small.shape).astype(np.uint8)
    quantized = cv2.resize(quantized_small, (w, h), interpolation=cv2.INTER_NEAREST)

    # For each color cluster, find regions of that color and check rectangularity
    for ci in range(k_colors):
        center_color = centers[ci].astype(np.uint8)
        # Create mask: pixels close to this cluster center
        diff = cv2.absdiff(quantized, center_color.reshape(1, 1, 3))
        dist = diff.sum(axis=2).astype(np.uint8)
        _, cmask = cv2.threshold(dist, 15, 255, cv2.THRESH_BINARY_INV)
        k_m = np.ones((7, 7), np.uint8)
        cmask = cv2.morphologyEx(cmask, cv2.MORPH_CLOSE, k_m, iterations=2)
        cmask = cv2.morphologyEx(cmask, cv2.MORPH_OPEN, np.ones((5,5),np.uint8))

        num_l, labels_c, stats_c, _ = cv2.connectedComponentsWithStats(cmask, connectivity=8)
        for lid in range(1, num_l):
            area = int(stats_c[lid, cv2.CC_STAT_AREA])
            if area < total * 0.0003 or area > total * 0.12:
                continue
            mask = np.zeros((h, w), np.uint8)
            mask[labels_c == lid] = 255
            cf, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if not cf:
                continue
            c = max(cf, key=cv2.contourArea)
            rect_score = rectangularity(c)
            if rect_score < MIN_RECT_SCORE:
                continue
            if not aspect_ratio_ok(c):
                continue
            if is_mostly_green(img, c, h, w):
                continue
            r = contour_to_plot(c, h, w, f"quant_{ci}_{lid}", min_ratio=0.0003)
            if r:
                r["confidence"] = min(0.88, 0.50 + rect_score * 0.4)
                results.append(r)

    return results


# ─────────────────────────────────────────────────────────────────────────────
#  MODE B — 2D CAD drawing detection
# ─────────────────────────────────────────────────────────────────────────────

def detect_2d_mode(img: np.ndarray) -> List[Dict]:
    h, w = img.shape[:2]
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8,8))
    enhanced = clahe.apply(gray)
    best: List[Dict] = []

    for gap in [3, 5, 7, 10, 14]:
        block = max(11, (min(h,w)//60)|1)
        adap = cv2.adaptiveThreshold(enhanced, 255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, block, 6)
        _, otsu = cv2.threshold(enhanced, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        lines = cv2.bitwise_or(adap, otsu)
        k = np.ones((gap, gap), np.uint8)
        thick = cv2.dilate(lines, k, iterations=2)
        not_lines = cv2.bitwise_not(thick)
        k_o = np.ones((max(2,gap//3), max(2,gap//3)), np.uint8)
        cleaned = cv2.morphologyEx(not_lines, cv2.MORPH_OPEN, k_o)

        num_l, labels, stats, _ = cv2.connectedComponentsWithStats(cleaned, connectivity=8)
        total = h * w
        results: List[Dict] = []
        for lid in range(1, num_l):
            area = int(stats[lid, cv2.CC_STAT_AREA])
            if area < total * 0.0002 or area > total * 0.15:
                continue
            mask = np.zeros((h,w), np.uint8)
            mask[labels==lid] = 255
            cf, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if not cf:
                continue
            c = max(cf, key=cv2.contourArea)
            r = contour_to_plot(c, h, w, f"2d_{gap}_{lid}")
            if r:
                results.append(r)

        if len(results) > len(best):
            best = results
        if len(results) >= 20:
            break

    return best


# ─────────────────────────────────────────────────────────────────────────────
#  Public API
# ─────────────────────────────────────────────────────────────────────────────

def detect_plots(image_bytes: bytes) -> List[Dict[str, Any]]:
    img = load_image(image_bytes)
    h, w = img.shape[:2]
    photo = is_photorealistic(img)

    candidates = detect_photo_mode(img) if photo else detect_2d_mode(img)

    # Fallback cross-mode
    if len(candidates) < 10:
        candidates += (detect_2d_mode(img) if photo else detect_photo_mode(img))

    if not candidates:
        return []

    unique = deduplicate(candidates, h, w)

    final: List[Dict[str, Any]] = []
    for idx, cand in enumerate(unique):
        plot_num, _ = run_ocr(img, cand["points"])
        has_num = plot_num is not None
        is_rect = cand["sides"] == 4
        conf = 0.92 if (is_rect and has_num) else (
               0.82 if has_num else (
               0.65 if is_rect else 0.45))
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
#  Debug pipeline
# ─────────────────────────────────────────────────────────────────────────────

def debug_pipeline(image_bytes: bytes) -> Dict[str, Any]:
    img = load_image(image_bytes)
    h, w = img.shape[:2]
    photo = is_photorealistic(img)

    def b64(arr: np.ndarray) -> str:
        _, buf = cv2.imencode(".png", arr)
        return base64.b64encode(buf).decode()

    smooth = cv2.bilateralFilter(img, 9, 75, 75)
    gray_s = cv2.cvtColor(smooth, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray_s, 40, 110)
    k = np.ones((9,9), np.uint8)
    closed_edges = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, k, iterations=2)

    # Color quantisation preview
    small = cv2.resize(img, (min(w,600), min(h, int(h*600/w))))
    data = small.reshape((-1,3)).astype(np.float32)
    criteria = (cv2.TERM_CRITERIA_EPS+cv2.TERM_CRITERIA_MAX_ITER, 20, 1.0)
    _, lbl, ctrs = cv2.kmeans(data, 8, None, criteria, 3, cv2.KMEANS_RANDOM_CENTERS)
    quant_small = ctrs[lbl.flatten()].reshape(small.shape).astype(np.uint8)
    quant = cv2.resize(quant_small, (w, h), interpolation=cv2.INTER_NEAREST)

    plots = detect_plots(image_bytes)
    annotated = img.copy()
    for p in plots:
        pts = np.array([[int(pt["x"]*w), int(pt["y"]*h)] for pt in p["points"]], np.int32)
        cv2.polylines(annotated, [pts], True, (0,220,60), 2)
        cx = int(sum(pt["x"] for pt in p["points"])/len(p["points"])*w)
        cy = int(sum(pt["y"] for pt in p["points"])/len(p["points"])*h)
        cv2.putText(annotated, p["plot_number"] or "?", (cx-10,cy+5),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.35, (0,0,255), 1)

    return {
        "original":       b64(img),
        "bilateral_smooth": b64(smooth),
        "edges_canny":    b64(edges),
        "closed_edges":   b64(closed_edges),
        "color_quantized": b64(quant),
        "annotated":      b64(annotated),
        "total_detected": len(plots),
        "mode": "3D render (bilateral+quantize)" if photo else "2D drawing (edge+CC)",
    }
