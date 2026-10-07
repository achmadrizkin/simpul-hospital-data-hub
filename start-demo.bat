@echo off
setlocal
cd /d "%~dp0"

echo [Simpul] Menyiapkan backend...
if not exist backend\.venv (
    py -m venv backend\.venv || python -m venv backend\.venv
)
backend\.venv\Scripts\python -m pip install -q -r backend\requirements.txt || goto :error

if not exist frontend\dist\index.html (
    echo [Simpul] Menyiapkan tampilan ^(sekali saja^)...
    pushd frontend
    call npm install --no-audit --no-fund || goto :error
    call npm run build || goto :error
    popd
)

echo.
echo [Simpul] Siap. Buka http://localhost:8000 di browser.
echo [Simpul] Tekan Ctrl+C untuk berhenti.
echo.
start "" http://localhost:8000
cd backend
.venv\Scripts\python -m uvicorn app.main:app --port 8000
echo.
echo [Simpul] Server berhenti.
pause
goto :eof

:error
echo.
echo [Simpul] Gagal menyiapkan. Pastikan Python 3.11+ dan Node.js 18+ sudah terpasang.
pause
