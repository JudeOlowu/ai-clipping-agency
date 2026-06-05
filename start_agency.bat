@echo off
title AI Clipping Agency Controller
echo ===================================================
echo      Starting AI Clipping Agency Services...
echo ===================================================
echo.

echo [1/3] Starting Backend (FastAPI)...
start "Agency Backend" cmd /c "cd dashboard\backend && uvicorn main:app --host 0.0.0.0 --port 8000 --reload"

echo [2/3] Starting Frontend (React)...
start "Agency Frontend" cmd /c "cd dashboard\frontend && npm run dev"

echo [3/3] Starting Background Scout Agent...
start "Scout Agent" cmd /c "python scout_agent.py"

echo.
echo ===================================================
echo SUCCESS: All services are booting up!
echo ===================================================
echo.
echo - Dashboard UI: http://localhost:5173
echo - Backend API: http://localhost:8000
echo.
echo Keep the new command windows open to keep the agency running.
echo You can close this specific setup window now.
pause
