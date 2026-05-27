from __future__ import annotations

import re
from typing import Optional, Tuple

import numpy as np
import pytesseract
from PIL import Image
import cv2


def extract_plot_number(image_region: np.ndarray) -> Tuple[Optional[str], float]:
    """
    Run Tesseract OCR on an image region and extract a plot number.
    Returns (plot_number, confidence) where confidence is 0-1.
    """
    if image_region is None or image_region.size == 0:
        return None, 0.0

    h, w = image_region.shape[:2]
    if h < 8 or w < 8:
        return None, 0.0

    # Upscale small regions for better OCR
    scale = max(1, min(4, 60 // min(h, w)))
    if scale > 1:
        image_region = cv2.resize(
            image_region, (w * scale, h * scale), interpolation=cv2.INTER_CUBIC
        )

    # Convert to grayscale if needed
    if len(image_region.shape) == 3:
        gray = cv2.cvtColor(image_region, cv2.COLOR_BGR2GRAY)
    else:
        gray = image_region

    # Apply thresholding to improve text clarity
    _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    # Run OCR with page segmentation mode 6 (single uniform block of text)
    config = "--psm 6 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-/ "
    pil_img = Image.fromarray(thresh)
    raw_text = pytesseract.image_to_string(pil_img, config=config).strip()

    # Also try inverted image if nothing found
    if not raw_text:
        inv = cv2.bitwise_not(thresh)
        pil_inv = Image.fromarray(inv)
        raw_text = pytesseract.image_to_string(pil_inv, config=config).strip()

    plot_number = parse_plot_number(raw_text)
    confidence = 0.85 if plot_number else 0.2

    return plot_number, confidence


def parse_plot_number(raw_text: str) -> Optional[str]:
    """Extract plot number pattern from raw OCR text."""
    if not raw_text:
        return None

    text = raw_text.upper().strip()

    patterns = [
        r"[A-Z]{1,2}-\d{1,4}",
        r"[A-Z]\d{1,3}",
        r"\d{1,4}[A-Z]{0,2}",
        r"\d{1,4}",
    ]

    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(0)

    return None
