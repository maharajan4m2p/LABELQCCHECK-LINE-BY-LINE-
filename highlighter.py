"""Draw only actual changed/missing/extra OCR lines."""
from pathlib import Path
import cv2

STATUS_COLORS = {
    "CHANGED": (0, 80, 255),
    "MISSING": (0, 165, 255),
    "EXTRA": (255, 150, 0),
}


def _draw_line(image, line, status, label):
    words = line.get("words", []) if line else []
    if not words:
        return

    x1 = min(int(w.get("x", 0)) for w in words)
    y1 = min(int(w.get("y", 0)) for w in words)
    x2 = max(int(w.get("x2", w.get("x", 0) + w.get("w", 0))) for w in words)
    y2 = max(int(w.get("y2", w.get("y", 0) + w.get("h", 0))) for w in words)
    if x2 <= x1 or y2 <= y1:
        return

    color = STATUS_COLORS.get(status, (0, 80, 255))
    pad = 8
    x1 = max(0, x1 - pad); y1 = max(0, y1 - pad)
    x2 = min(image.shape[1] - 1, x2 + pad); y2 = min(image.shape[0] - 1, y2 + pad)
    cv2.rectangle(image, (x1, y1), (x2, y2), color, 3)
    cv2.rectangle(image, (x1, max(0, y1 - 25)), (min(image.shape[1] - 1, x1 + 105), y1), color, -1)
    cv2.putText(image, label, (x1 + 5, max(15, y1 - 7)), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1, cv2.LINE_AA)


def make_highlighted(page_image, output_path, comparison_rows, side):
    image = cv2.imread(str(page_image), cv2.IMREAD_COLOR)
    if image is None:
        return None

    for row in comparison_rows:
        status = row.get("status")
        if side == "approval" and status in ("CHANGED", "MISSING"):
            _draw_line(
                image,
                {"words": row.get("approval_words", [])},
                status,
                f"{status} #{row.get('row')}",
            )
        elif side == "sample" and status in ("CHANGED", "EXTRA"):
            _draw_line(
                image,
                {"words": row.get("sample_words", [])},
                status,
                f"{status} #{row.get('row')}",
            )

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(output_path), image, [int(cv2.IMWRITE_JPEG_QUALITY), 94])
    return output_path
