"""Robust Tesseract OCR with line/word coordinates for label QC."""
from pathlib import Path
import logging
import os
import re
import shutil

import cv2
import pytesseract

from config import (
    OCR_FALLBACK_PSM,
    OCR_LANGUAGE,
    OCR_MIN_CONFIDENCE,
    OCR_PSM,
    TESSERACT_TIMEOUT,
)

logger = logging.getLogger(__name__)


def clean_text(value):
    value = str(value or "").replace("\x0c", " ").replace("\u00a0", " ")
    return re.sub(r"\s+", " ", value).strip()


def is_useful_text(text):
    s = clean_text(text)
    if not s:
        return False
    compact = re.sub(r"[^A-Za-z0-9%]+", "", s)
    if len(compact) < 3:
        return False
    if not any(ch.isalnum() for ch in s):
        return False
    return len(compact) / max(1, len(s)) >= 0.35


class OCREngine:
    def __init__(self):
        self.language = OCR_LANGUAGE or "eng"
        self.psm = int(OCR_PSM or 6)
        self.fallback_psm = int(OCR_FALLBACK_PSM or 11)
        self.min_confidence = float(OCR_MIN_CONFIDENCE or 0)
        self.timeout = max(10, int(os.getenv("TESSERACT_TIMEOUT", TESSERACT_TIMEOUT)))
        self.is_render = bool(os.getenv("RENDER") or os.getenv("RENDER_SERVICE_ID"))
        self.tesseract_path = self._find_tesseract()
        self._available = None

        if self.tesseract_path:
            pytesseract.pytesseract.tesseract_cmd = self.tesseract_path
            logger.info("Tesseract candidate: %s", self.tesseract_path)

    def _find_tesseract(self):
        """Find Tesseract on Windows, Linux, Render, or through TESSERACT_CMD."""
        candidates = []

        env_cmd = os.getenv("TESSERACT_CMD")
        if env_cmd:
            candidates.append(env_cmd.strip().strip('"'))

        found = shutil.which("tesseract")
        if found:
            candidates.append(found)

        if os.name == "nt":
            candidates.extend([
                r"C:\Program Files\Tesseract-OCR\tesseract.exe",
                r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
                os.path.expandvars(r"%LOCALAPPDATA%\Programs\Tesseract-OCR\tesseract.exe"),
                os.path.expandvars(r"%USERPROFILE%\AppData\Local\Programs\Tesseract-OCR\tesseract.exe"),
            ])
        else:
            candidates.extend([
                "/usr/bin/tesseract",
                "/usr/local/bin/tesseract",
            ])

        seen = set()
        for candidate in candidates:
            if not candidate or candidate in seen:
                continue
            seen.add(candidate)
            if Path(candidate).is_file():
                return candidate

        return None

    def is_tesseract_available(self):
        if self._available is not None:
            return self._available

        if not self.tesseract_path:
            logger.error(
                "Tesseract not found. Install Tesseract OCR or set TESSERACT_CMD."
            )
            self._available = False
            return False

        try:
            version = pytesseract.get_tesseract_version()
            logger.info("Tesseract detected: %s", version)
            self._available = True
        except Exception as exc:
            logger.error("Tesseract cannot start: %s", exc)
            self._available = False

        return self._available

    def load_image(self, path):
        image = cv2.imread(str(Path(path)), cv2.IMREAD_COLOR)
        if image is None or image.size == 0:
            raise ValueError(f"Unable to read image: {Path(path).name}")
        return image

    def resize_for_ocr(self, image):
        h, w = image.shape[:2]
        max_dim = max(h, w)
        target = 2400 if self.is_render else 3000
        if max_dim <= target:
            return image

        scale = target / float(max_dim)
        return cv2.resize(
            image,
            (max(1, int(w * scale)), max(1, int(h * scale))),
            interpolation=cv2.INTER_AREA,
        )

    def preprocess(self, image):
        image = self.resize_for_ocr(image)
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(gray)
        return image, clahe

    def _data_pass(self, image, psm):
        try:
            data = pytesseract.image_to_data(
                image,
                lang=self.language,
                config=f"--oem 3 --psm {int(psm)}",
                output_type=pytesseract.Output.DICT,
                timeout=self.timeout,
            )
        except Exception as exc:
            logger.warning("Tesseract PSM-%s failed: %s", psm, exc)
            return [], []

        words = []
        count = len(data.get("text", []))

        for i in range(count):
            text = clean_text(data["text"][i])
            if not text:
                continue

            try:
                conf = float(data.get("conf", [0] * count)[i])
                x = int(data["left"][i])
                y = int(data["top"][i])
                w = int(data["width"][i])
                h = int(data["height"][i])
                block = int(data.get("block_num", [0] * count)[i])
                par = int(data.get("par_num", [0] * count)[i])
                line = int(data.get("line_num", [0] * count)[i])
            except Exception:
                continue

            if w <= 0 or h <= 0 or conf < self.min_confidence:
                continue

            words.append({
                "text": text,
                "confidence": round(max(0.0, conf), 1),
                "x": x,
                "y": y,
                "w": w,
                "h": h,
                "x2": x + w,
                "y2": y + h,
                "block_num": block,
                "par_num": par,
                "line_num": line,
            })

        groups = {}
        for word in words:
            key = (word["block_num"], word["par_num"], word["line_num"])
            groups.setdefault(key, []).append(word)

        ordered = sorted(
            groups.values(),
            key=lambda group: (
                min(w["y"] for w in group),
                min(w["x"] for w in group),
            ),
        )

        lines = []

        for line_index, group in enumerate(ordered, start=1):
            group.sort(key=lambda item: item["x"])

            for word_index, word in enumerate(group, start=1):
                word["line_index"] = line_index
                word["word_index"] = word_index

            text = " ".join(w["text"] for w in group)

            if not is_useful_text(text):
                continue

            confidence = sum(w["confidence"] for w in group) / len(group)
            if confidence < 10:
                continue

            lines.append({
                "line_index": line_index,
                "text": text,
                "confidence": round(confidence, 1),
                "words": group,
            })

        return words, lines

    def extract_page(self, path, page_number=1):
        if not self.is_tesseract_available():
            raise RuntimeError(
                "Tesseract OCR is not installed/configured. "
                "Install Tesseract OCR and restart the application."
            )

        image = self.load_image(path)
        original_h, original_w = image.shape[:2]

        ocr_image, enhanced = self.preprocess(image)

        words, lines = self._data_pass(ocr_image, self.psm)
        used_psm = self.psm

        if not lines:
            words, lines = self._data_pass(enhanced, self.fallback_psm)
            used_psm = self.fallback_psm

        sx = original_w / max(1, ocr_image.shape[1])
        sy = original_h / max(1, ocr_image.shape[0])

        mapped_words = []

        for word in words:
            item = dict(word)
            item["x"] = int(round(word["x"] * sx))
            item["y"] = int(round(word["y"] * sy))
            item["w"] = max(1, int(round(word["w"] * sx)))
            item["h"] = max(1, int(round(word["h"] * sy)))
            item["x2"] = item["x"] + item["w"]
            item["y2"] = item["y"] + item["h"]
            item["page"] = page_number
            mapped_words.append(item)

        # Use the mapped word coordinates to rebuild the lines.
        by_line = {}

        for word in mapped_words:
            by_line.setdefault(word["line_index"], []).append(word)

        mapped_lines = []
        display_line = 0

        for _, group in sorted(by_line.items()):
            group.sort(key=lambda item: item["x"])
            text = " ".join(w["text"] for w in group)

            if not is_useful_text(text):
                continue

            confidence = sum(w["confidence"] for w in group) / len(group)
            if confidence < 10:
                continue

            display_line += 1

            for word_index, word in enumerate(group, start=1):
                word["display_line_index"] = display_line
                word["word_index"] = word_index

            mapped_lines.append({
                "line_index": display_line,
                "page": page_number,
                "text": text,
                "confidence": round(confidence, 1),
                "words": group,
            })

        text = "\n".join(line["text"] for line in mapped_lines)

        confidence = (
            round(
                sum(w["confidence"] for w in mapped_words)
                / len(mapped_words),
                1,
            )
            if mapped_words
            else 0.0
        )

        logger.info(
            "OCR page=%s psm=%s words=%s lines=%s confidence=%.1f",
            page_number,
            used_psm,
            len(mapped_words),
            len(mapped_lines),
            confidence,
        )

        return {
            "page": page_number,
            "text": text,
            "words": mapped_words,
            "lines": mapped_lines,
            "confidence": confidence,
            "engine": "tesseract",
            "psm": used_psm,
            "image_width": original_w,
            "image_height": original_h,
        }

    def extract_document(self, page_records):
        if not self.is_tesseract_available():
            raise RuntimeError(
                "Tesseract OCR is not available. "
                "Install Tesseract OCR or set TESSERACT_CMD to the "
                "full path of tesseract.exe, then restart Flask."
            )

        all_words = []
        all_lines = []
        texts = []
        confidence_values = []
        global_line = 0

        for page in page_records:
            result = self.extract_page(
                page["image_path"],
                page["page"],
            )

            for line in result["lines"]:
                global_line += 1
                item = dict(line)
                item["global_line"] = global_line
                all_lines.append(item)

            all_words.extend(result["words"])

            if result["text"]:
                texts.append(result["text"])

            if result["confidence"]:
                confidence_values.append(result["confidence"])

        return {
            "text": "\n".join(texts),
            "lines": all_lines,
            "words": all_words,
            "confidence": (
                round(
                    sum(confidence_values) / len(confidence_values),
                    1,
                )
                if confidence_values
                else 0.0
            ),
            "engine": "tesseract",
            "pages": len(page_records),
        }
