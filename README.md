# Label QC Checker Pro — Line-by-Line + PDF

## What this version does

1. Upload one Approval/Master image or PDF.
2. Upload one or more Sample images or PDFs.
3. PDF files are rendered page-by-page using PyMuPDF.
4. Tesseract reads the text while preserving line and word coordinates.
5. Every meaningful OCR line is compared in document order.
6. The result is classified as:
   - MATCHED
   - CHANGED
   - MISSING
   - EXTRA
7. Changed, missing and extra lines are highlighted on the corresponding images.
8. CSV and JSON reports are available.
9. Care-symbol checking is supplementary and does not replace the line-by-line OCR result.

## Important comparison rule

The comparison engine does NOT use aggressive OCR correction when deciding if a line changed. It only ignores case and repeated whitespace. This prevents real differences such as `100% COTTON` vs `90% COTTON` from being incorrectly marked as matched.

## Run locally

```bash
pip install -r requirements.txt
python app.py
```

Tesseract must be installed and available on PATH.

## Deploy on Render

Push this folder to GitHub and create a Render Web Service using the included Dockerfile/render.yaml.

The service listens on Render's `$PORT` and has a `/health` endpoint.

## Test with the supplied samples

Approval:
`samples/approval_label.jpg`

Sample:
`samples/sample_label.jpg`

The result should show line-level differences such as:

- `100% COTTON` vs `90% COTTON` → CHANGED
- `NORMAL WASH` vs `HEAVY WASH` → CHANGED
- `MADE IN INDIA` vs `MADE IN USA` → CHANGED
- `ALLOWED` vs `NOT ALLOWED` → CHANGED

OCR can still make character-level mistakes on low-quality images; the application reports what OCR actually read.


## Windows OCR requirement

This project uses Tesseract OCR for line-by-line text extraction. `pytesseract` is only a Python wrapper; the Tesseract executable must also be installed.

The application automatically checks these locations:
- `tesseract` on PATH
- `C:\Program Files\Tesseract-OCR\tesseract.exe`
- `C:\Program Files (x86)\Tesseract-OCR\tesseract.exe`
- common per-user installation locations

If Tesseract is installed elsewhere, set:
```powershell
$env:TESSERACT_CMD="C:\full\path\to\tesseract.exe"
python app.py
```

A clear error is now shown instead of silently returning `0` OCR lines.

For Render, the Dockerfile installs `tesseract-ocr` and `tesseract-ocr-eng` automatically.


## Render deployment
1. Push this folder to GitHub.
2. In Render, create a **Web Service** from the repository.
3. Select **Docker**.
4. Keep `render.yaml` in the repository root, or use the included Render blueprint.
5. The Docker image installs Tesseract OCR and English language data automatically.
6. Open the Render URL and upload the approval/master plus one or more sample files.

The comparison is line-by-line. A line is reported as MATCHED, CHANGED, MISSING, or EXTRA. PDFs are rendered page-by-page before OCR.
