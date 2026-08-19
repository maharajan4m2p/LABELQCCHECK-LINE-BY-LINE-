import csv
import io
import json
import logging
import os
import time
import uuid
from datetime import datetime
from pathlib import Path

from flask import Flask, Response, jsonify, redirect, render_template, request, send_from_directory, url_for
from werkzeug.utils import secure_filename

from config import MAX_UPLOAD_MB, PASS_SCORE
from engine.comparison_engine import compare_lines
from engine.document_processor import is_supported, render_document
from engine.highlighter import make_highlighted
from engine.ocr_engine import OCREngine
from engine.visual_checker import care_symbol_difference

BASE = Path(__file__).resolve().parent
UPLOAD = BASE / "uploads"
OUTPUT = BASE / "outputs"
UPLOAD.mkdir(parents=True, exist_ok=True)
OUTPUT.mkdir(parents=True, exist_ok=True)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_MB * 1024 * 1024


def file_info(path: Path):
    return {"name": path.name, "size_kb": round(path.stat().st_size / 1024, 1)}


def allowed(file):
    return bool(file and file.filename and is_supported(file.filename))


def save_upload(file, job, role, index=0):
    safe = secure_filename(file.filename) or "upload"
    prefix = f"{job}_{role}_{index}_" if index else f"{job}_{role}_"
    path = UPLOAD / f"{prefix}{safe}"
    file.save(path)
    return path


def process_document(path, job, role, ocr):
    page_dir = OUTPUT / job / role / "pages"
    pages = render_document(path, page_dir)
    result = ocr.extract_document(pages)
    result["page_records"] = pages
    result["highlight_dir"] = OUTPUT / job / role / "highlighted"
    return result


def build_highlights(job, role, ocr_result, rows):
    outputs = []
    out_dir = ocr_result["highlight_dir"]
    out_dir.mkdir(parents=True, exist_ok=True)

    for page in ocr_result.get("page_records", []):
        page_rows = []
        for row in rows:
            key = f"{role}_page"
            if row.get(key) == page["page"]:
                page_rows.append(row)

        out = out_dir / f"page_{page['page']:03d}.jpg"
        make_highlighted(page["image_path"], out, page_rows, role)
        outputs.append({
            "page": page["page"],
            "name": out.name,
            "url_name": f"{job}/{role}/highlighted/{out.name}",
        })
    return outputs


def safe_json_write(path: Path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


@app.get("/")
def index():
    return render_template("index.html")


@app.post("/compare")
def compare():
    started = time.perf_counter()
    approval = request.files.get("approval")
    samples = [f for f in request.files.getlist("samples") if f and f.filename]

    if not allowed(approval):
        return render_template(
            "index.html",
            error="Approval/master must be JPG, JPEG, PNG, WEBP, BMP, TIFF or PDF.",
        )

    samples = [f for f in samples if allowed(f)]
    if not samples:
        return render_template(
            "index.html",
            error="Please upload at least one valid sample image or PDF.",
        )

    job = uuid.uuid4().hex[:10]
    approval_path = save_upload(approval, job, "APPROVAL")
    sample_paths = [save_upload(f, job, "SAMPLE", i) for i, f in enumerate(samples, 1)]
    ocr = OCREngine()

    try:
        approval_ocr = process_document(approval_path, job, "approval", ocr)
    except Exception as exc:
        logger.exception("Approval processing failed")
        return render_template("index.html", error=f"Approval processing failed: {exc}"), 400

    results = []

    for i, sample_path in enumerate(sample_paths, 1):
        sample_role = f"sample_{i}"
        try:
            sample_ocr = process_document(sample_path, job, sample_role, ocr)
            comparison = compare_lines(approval_ocr, sample_ocr)

            # Visual care-symbol check is supplementary. It never replaces line OCR.
            visual = None
            if approval_ocr.get("page_records") and sample_ocr.get("page_records"):
                visual = care_symbol_difference(
                    approval_ocr["page_records"][0]["image_path"],
                    sample_ocr["page_records"][0]["image_path"],
                )
                comparison["visual_check"] = visual

            approval_highlights = build_highlights(
                job, "approval", approval_ocr, comparison["rows"]
            )
            sample_highlights = build_highlights(
                job, sample_role, sample_ocr, comparison["rows"]
            )

            report_payload = {
                "job": job,
                "sample_index": i,
                "generated_at": datetime.now().isoformat(timespec="seconds"),
                "approval_file": file_info(approval_path),
                "sample_file": file_info(sample_path),
                "comparison": comparison,
            }
            safe_json_write(OUTPUT / job / f"report_{i}.json", report_payload)

            results.append({
                "index": i,
                "filename": sample_path.name,
                "comparison": comparison,
                "approval_ocr": approval_ocr,
                "sample_ocr": sample_ocr,
                "approval_highlights": approval_highlights,
                "sample_highlights": sample_highlights,
                "approval_info": file_info(approval_path),
                "sample_info": file_info(sample_path),
                "processing_time": round(time.perf_counter() - started, 2),
            })
        except Exception as exc:
            logger.exception("Sample %s processing failed", i)
            results.append({
                "index": i,
                "filename": sample_path.name,
                "error": str(exc),
                "processing_time": round(time.perf_counter() - started, 2),
            })

    comparison_id = f"CMP-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{job.upper()}"
    return render_template(
        "results.html",
        job=job,
        comparison_id=comparison_id,
        checked_on=datetime.now().strftime("%d %b %Y %I:%M %p"),
        approval_name=approval_path.name,
        results=results,
        pass_score=PASS_SCORE,
    )


@app.get("/outputs/<path:name>")
def outputs(name):
    return send_from_directory(OUTPUT, name)


@app.get("/report/<job>/<int:index>.json")
def report_json(job, index):
    path = OUTPUT / job / f"report_{index}.json"
    if not path.exists():
        return jsonify({"error": "Report not found"}), 404
    return send_from_directory(path.parent, path.name, as_attachment=True)


@app.get("/report/<job>/<int:index>.csv")
def report_csv(job, index):
    path = OUTPUT / job / f"report_{index}.json"
    if not path.exists():
        return jsonify({"error": "Report not found"}), 404

    data = json.loads(path.read_text(encoding="utf-8"))
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([
        "Row", "Status", "Approval Page", "Approval Line", "Approval Text",
        "Sample Page", "Sample Line", "Sample Text", "Similarity %",
        "Approval Confidence %", "Sample Confidence %",
    ])

    for row in data["comparison"]["rows"]:
        writer.writerow([
            row["row"], row["status"], row.get("approval_page", ""),
            row.get("approval_line", ""), row.get("approval", ""),
            row.get("sample_page", ""), row.get("sample_line", ""),
            row.get("sample", ""), round(row.get("similarity", 0) * 100, 1),
            row.get("approval_confidence", ""), row.get("sample_confidence", ""),
        ])

    return Response(
        buf.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={job}_line_by_line_{index}.csv"},
    )


@app.get("/health")
def health():
    return jsonify({"status": "ok", "service": "Label QC Checker Pro", "version": "line-by-line-pdf"})


@app.errorhandler(413)
def too_large(_):
    return render_template("index.html", error=f"File is too large. Maximum upload is {MAX_UPLOAD_MB} MB."), 413


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")), debug=False)
