@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  python -m venv .venv
  if errorlevel 1 goto failed
)
".venv\Scripts\python.exe" -c "import fastapi,sqlalchemy,cv2,bcrypt,httpx" >nul 2>&1
if errorlevel 1 (
  ".venv\Scripts\python.exe" -m pip install -r requirements.txt -r requirements-ai.txt
  if errorlevel 1 goto failed
)
".venv\Scripts\python.exe" -m ai_service.download_model
if errorlevel 1 goto failed
".venv\Scripts\python.exe" scripts\show_start.py
if errorlevel 1 goto failed
pause
exit /b
:failed
echo 启动失败，请查看上面的提示。
pause
exit /b 1
