@echo off
echo Starting Cab Fare Comparator...
echo Please wait a moment while the app loads.

:: Start backend (FastAPI)
start "Backend" cmd /k "cd backend && ..\venv\Scripts\activate && uvicorn api:app --host 127.0.0.1 --port 8000 --reload"

:: Start frontend (Vite dev server)
start "Frontend" cmd /k "cd frontend && npm run dev"

pause
