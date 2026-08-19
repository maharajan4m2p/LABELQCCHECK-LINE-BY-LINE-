# Run PowerShell as Administrator if your company policy permits it.
# This installs Tesseract OCR using winget, if winget is available.
$ErrorActionPreference = "Stop"
Write-Host "Checking for winget..."
if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
    Write-Host "winget is not available. Install Tesseract OCR manually from:"
    Write-Host "https://github.com/UB-Mannheim/tesseract/wiki"
    exit 1
}
winget install --id UB-Mannheim.TesseractOCR --accept-source-agreements --accept-package-agreements
Write-Host "Tesseract installation completed. Close and reopen VS Code, then run: python app.py"
