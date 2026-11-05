@echo off
rem Build "Joy OSC.exe" (one file, no install needed) into releases\.
rem Run on a Windows PC. Needs internet the first time.
setlocal
cd /d "%~dp0"

where uv >nul 2>nul
if errorlevel 1 (
  echo Installing uv ^(Python manager^)...
  powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
  set "PATH=%USERPROFILE%\.local\bin;%PATH%"
)

uv venv -q --allow-existing -p 3.12 .build-venv || goto :fail
uv pip install -q -p .build-venv -r requirements.txt pyinstaller || goto :fail

.build-venv\Scripts\pyinstaller --noconfirm --clean --onefile --windowed ^
  --name "Joy OSC" --distpath build\dist --workpath build\work --specpath build ^
  joy_osc_app.py || goto :fail

if not exist releases mkdir releases
copy /y "build\dist\Joy OSC.exe" "releases\Joy-OSC-windows.exe" >nul
echo Done: releases\Joy-OSC-windows.exe
pause
exit /b 0

:fail
echo Build failed.
pause
exit /b 1
