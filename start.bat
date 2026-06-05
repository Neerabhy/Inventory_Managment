@echo off
setlocal

echo ==========================================================
echo Starting ElectroInventory v3 (Backend + Frontend)
echo ==========================================================

REM Create a new window for the Backend
echo Starting FastAPI Backend...
start "ElectroInventory Backend" cmd /c "cd api-backend & python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000"

REM Wait a bit for backend to start
timeout /t 3 /nobreak >nul

REM Start the Frontend in the web-frontend folder
echo Starting React Frontend...
cd web-frontend & npm run dev
