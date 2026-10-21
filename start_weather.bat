@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo [观云台] 正在创建 Python 虚拟环境...
  python -m venv .venv
  if errorlevel 1 goto :error

  echo [观云台] 正在安装项目依赖...
  ".venv\Scripts\python.exe" -m pip install -r requirements.txt
  if errorlevel 1 goto :error
)

echo [观云台] 网站即将在浏览器中打开：
echo http://127.0.0.1:5000
start "" powershell -NoProfile -WindowStyle Hidden -Command "Start-Sleep -Seconds 2; Start-Process 'http://127.0.0.1:5000'"
".venv\Scripts\python.exe" manage.py run --host 127.0.0.1 --port 5000
goto :eof

:error
echo.
echo 启动失败，请确认已安装 Python 3.10 或更高版本。
pause
exit /b 1
