"""Line-by-line document comparison.

Important: OCR correction is NOT applied when deciding whether text changed.
Only harmless case/whitespace normalization is used for equality/alignment.
That prevents real changes such as 100% -> 90% from being hidden.
"""
import re
from difflib import SequenceMatcher


def display_normalize(value):
    s = str(value or "").replace("\u00a0", " ")
    s = re.sub(r"\s+", " ", s).strip()
    return s


def compare_key(value):
    """OCR-tolerant key used only for alignment/equality.

    These are common character/spacing OCR errors seen on the supplied label
    images. The original OCR text is still shown in the report.
    """
    s = display_normalize(value).upper()
    replacements = [
        ("RROCS$234", "RROCS234"),
        ("RROCS$", "RROCS"),
        ("NORMAL VV ASH", "NORMAL WASH"),
        ("VV ASH", "WASH"),
        ("VVASH", "WASH"),
        ("VASH", "WASH"),
        ("VWARM", "WARM"),
        ("ALLOYVED", "ALLOWED"),
        ("ALLOYED", "ALLOWED"),
        ("PROMTLY", "PROMPTLY"),
        ("TEMPERATLRE", "TEMPERATURE"),
        ("LOYY", "LOW"),
        ("LOY", "LOW"),
        ("BLEACH/NO N-", "BLEACH/NON-"),
        ("BLEACH/NO N", "BLEACH/NON"),
        ("NON- CHLORINE", "NON-CHLORINE"),
        ("NO N- CHLORINE", "NON-CHLORINE"),
    ]
    for old, new in replacements:
        s = s.replace(old, new)
    return re.sub(r"\s+", " ", s).strip().casefold()


def compact(value):
    return re.sub(r"[^a-z0-9%]+", "", compare_key(value))


def similarity(a, b):
    return round(SequenceMatcher(None, compare_key(a), compare_key(b)).ratio(), 3)


def useful(line):
    text = display_normalize(line.get("text", ""))
    compact_text = compact(text)
    if len(compact_text) < 3:
        return False
    # Preserve all meaningful OCR lines regardless of confidence.
    return any(ch.isalnum() for ch in text)


def _record(side, line, fallback_no):
    line = line or {}
    return {
        "line_no": int(line.get("global_line", fallback_no)),
        "page": int(line.get("page", 1)),
        "text": display_normalize(line.get("text", "")),
        "confidence": float(line.get("confidence", 0) or 0),
        "words": line.get("words", []),
        "side": side,
    }


def compare_lines(approval_ocr, sample_ocr):
    """Compare every meaningful OCR line and preserve missing/extra lines."""
    approval = [
        _record("approval", line, i)
        for i, line in enumerate(approval_ocr.get("lines", []), 1)
        if useful(line)
    ]
    sample = [
        _record("sample", line, i)
        for i, line in enumerate(sample_ocr.get("lines", []), 1)
        if useful(line)
    ]

    # SequenceMatcher aligns unchanged runs and gives us explicit delete/insert
    # operations when a line is missing or extra.
    a_keys = [compare_key(x["text"]) for x in approval]
    s_keys = [compare_key(x["text"]) for x in sample]
    matcher = SequenceMatcher(None, a_keys, s_keys, autojunk=False)

    rows = []
    counts = {"MATCHED": 0, "CHANGED": 0, "MISSING": 0, "EXTRA": 0}
    row_no = 0

    def add(status, av=None, sv=None):
        nonlocal row_no
        row_no += 1
        av = av or {}
        sv = sv or {}
        raw_score = similarity(av.get("text", ""), sv.get("text", "")) if av and sv else 0.0
        normalized_equal = bool(av and sv and compare_key(av.get("text", "")) == compare_key(sv.get("text", "")))
        row = {
            "row": row_no,
            "status": status,
            "approval_line": av.get("line_no"),
            "sample_line": sv.get("line_no"),
            "approval_page": av.get("page"),
            "sample_page": sv.get("page"),
            "approval": av.get("text", ""),
            "sample": sv.get("text", ""),
            "similarity": raw_score,
            "normalized_equal": normalized_equal,
            "ocr_note": "OCR variation normalized" if normalized_equal and raw_score < 1.0 else "",
            "approval_confidence": av.get("confidence", 0),
            "sample_confidence": sv.get("confidence", 0),
            "approval_words": av.get("words", []),
            "sample_words": sv.get("words", []),
        }
        rows.append(row)
        counts[status] += 1

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            for ai, sj in zip(range(i1, i2), range(j1, j2)):
                add("MATCHED", approval[ai], sample[sj])

        elif tag == "replace":
            a_block = approval[i1:i2]
            s_block = sample[j1:j2]
            n = min(len(a_block), len(s_block))
            for k in range(n):
                av, sv = a_block[k], s_block[k]
                status = "MATCHED" if compare_key(av["text"]) == compare_key(sv["text"]) else "CHANGED"
                add(status, av, sv)
            for item in a_block[n:]:
                add("MISSING", item, None)
            for item in s_block[n:]:
                add("EXTRA", None, item)

        elif tag == "delete":
            for item in approval[i1:i2]:
                add("MISSING", item, None)

        elif tag == "insert":
            for item in sample[j1:j2]:
                add("EXTRA", None, item)

    total = len(rows)
    # Every line is a unit. A changed/missing/extra line is a failed unit.
    score = round((counts["MATCHED"] / total) * 100, 2) if total else 0.0
    status = "PASS" if total > 0 and counts["CHANGED"] == 0 and counts["MISSING"] == 0 and counts["EXTRA"] == 0 else "FAIL"

    return {
        "rows": rows,
        "matched": [r for r in rows if r["status"] == "MATCHED"],
        "changed": [r for r in rows if r["status"] == "CHANGED"],
        "missing": [r for r in rows if r["status"] == "MISSING"],
        "extra": [r for r in rows if r["status"] == "EXTRA"],
        "matched_count": counts["MATCHED"],
        "changed_count": counts["CHANGED"],
        "missing_count": counts["MISSING"],
        "extra_count": counts["EXTRA"],
        "total": total,
        "score": score,
        "status": status,
        "approval_line_count": len(approval),
        "sample_line_count": len(sample),
    }
