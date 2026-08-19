"""Supplementary visual comparison for care-symbol regions.

This check is intentionally independent from the OCR line score.
"""
import cv2
import numpy as np


def care_symbol_difference(approval_image, sample_image):
    try:
        a = cv2.imread(str(approval_image), cv2.IMREAD_GRAYSCALE)
        b = cv2.imread(str(sample_image), cv2.IMREAD_GRAYSCALE)
        if a is None or b is None:
            return {"changed": False, "difference": 0.0}

        h = min(a.shape[0], b.shape[0])
        w = min(a.shape[1], b.shape[1])
        if h < 100 or w < 100:
            return {"changed": False, "difference": 0.0}

        # A broad lower-middle band works as a secondary warning for the supplied
        # garment-label layout. It does not alter text line results.
        y1, y2 = int(h * 0.45), int(h * 0.68)
        x1, x2 = int(w * 0.08), int(w * 0.92)
        ac = cv2.resize(a[y1:y2, x1:x2], (700, 180), interpolation=cv2.INTER_AREA)
        bc = cv2.resize(b[y1:y2, x1:x2], (700, 180), interpolation=cv2.INTER_AREA)
        diff = float(np.mean(cv2.absdiff(ac, bc)))
        return {"changed": diff >= 18.0, "difference": round(diff, 2)}
    except Exception:
        return {"changed": False, "difference": 0.0}
