$ErrorActionPreference = "Stop"

Write-Host "Activating virtual environment..."
if (Test-Path "venv\Scripts\Activate.ps1") {
    . "venv\Scripts\Activate.ps1"
}

Write-Host "Installing PyInstaller..."
pip install pyinstaller

Write-Host "Finding CustomTkinter path..."
$ctk_path = python -c "import customtkinter, os; print(os.path.dirname(customtkinter.__file__))"

Write-Host "Building executable with PyInstaller..."
pyinstaller --noconfirm `
    --onedir `
    --windowed `
    --name "LLM_Quality_Evaluator" `
    --paths "." `
    --add-data "templates;templates" `
    --add-data "profiles;profiles" `
    --add-data "projects;projects" `
    --add-data "$ctk_path;customtkinter" `
    --collect-all "deepeval" `
    --hidden-import "pandas" `
    --hidden-import "pydantic" `
    ui/desktop/app.py

Write-Host "Build complete! Check the 'dist/LLM_Quality_Evaluator' folder."
