import os

OCR_LANGUAGE = os.getenv("OCR_LANGUAGE", "eng")
# PSM 6 is reliable for structured garment/carton labels.
OCR_PSM = int(os.getenv("OCR_PSM", "6"))
OCR_FALLBACK_PSM = int(os.getenv("OCR_FALLBACK_PSM", "11"))
OCR_MIN_CONFIDENCE = float(os.getenv("OCR_MIN_CONFIDENCE", "0"))
TESSERACT_TIMEOUT = int(os.getenv("TESSERACT_TIMEOUT", "25"))
MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "25"))
PDF_DPI = int(os.getenv("PDF_DPI", "220"))
LINE_MATCH_THRESHOLD = float(os.getenv("LINE_MATCH_THRESHOLD", "0.97"))
PASS_SCORE = float(os.getenv("PASS_SCORE", "100"))
# Lines with fewer than this many useful characters are usually symbol noise.
MIN_LINE_CHARS = int(os.getenv("MIN_LINE_CHARS", "3"))
