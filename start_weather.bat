@echo off
setlocal
cd /d "%~dp0"

set "APP_URL=http://127.0.0.1:5000"
set "PYTHON_EXE=%CD%\.venv\Scripts\python.exe"

rem If the service is already healthy, only open the browser.
powershell -NoProfile -Command "try { Invoke-RestMethod '%APP_URL%/api/health' -TimeoutSec 2 | Out-Null; exit 0 } catch { exit 1 }" >nul 2>&1
if not errorlevel 1 (
  echo Weather ML is already running at %APP_URL%
  start "" "%APP_URL%"
  exit /b 0
)

if not exist "%PYTHON_EXE%" goto setup
"%PYTHON_EXE%" --version >nul 2>&1
if errorlevel 1 goto setup
goto dependencies

:setup
echo Creating the Python virtual environment...
where py >nul 2>&1
if not errorlevel 1 (
  py -3 -m venv .venv
) else (
  python -m venv .venv
)
if errorlevel 1 goto error_python

:dependencies
"%PYTHON_EXE%" -c "import flask, joblib, numpy, pandas, requests, sklearn, waitress" >nul 2>&1
if not errorlevel 1 goto launch

echo Installing project dependencies...
"%PYTHON_EXE%" -m pip install -r requirements.txt
if errorlevel 1 goto error_dependencies

:launch
echo Starting Weather ML at %APP_URL%
echo Keep this window open while using the website.

rem Open the browser only after the Flask health endpoint responds.
start "" powershell -NoProfile -WindowStyle Hidden -Command "$url='%APP_URL%'; for ($i=0; $i -lt 40; $i++) { try { Invoke-RestMethod ($url + '/api/health') -TimeoutSec 1 | Out-Null; Start-Process $url; exit } catch { Start-Sleep -Milliseconds 500 } }"
"%PYTHON_EXE%" manage.py run --host 127.0.0.1 --port 5000
if errorlevel 1 goto error_server
exit /b 0

:error_python
echo.
echo Python 3.10 or newer was not found. Install Python and try again.
goto error

:error_dependencies
echo.
echo Project dependencies could not be installed. Check the network and try again.
goto error

:error_server
echo.
echo The local server stopped unexpectedly. Check the message above.

:error
pause
exit /b 1
