@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo Servidor: http://127.0.0.1:8000  (Ctrl+C para detener)
python -m uvicorn main:app --reload
if errorlevel 1 pause
