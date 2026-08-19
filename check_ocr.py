import os
from engine.ocr_engine import OCREngine

ocr = OCREngine()
print("Tesseract path:", ocr.tesseract_path)
print("Tesseract available:", ocr.is_tesseract_available())
if not ocr.is_tesseract_available():
    print("\nFIX:")
    print(r'PowerShell: $env:TESSERACT_CMD="C:\Program Files\Tesseract-OCR\tesseract.exe"')
    print("Then restart VS Code/terminal and run python app.py")
