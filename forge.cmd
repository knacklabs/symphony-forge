@echo off
setlocal
set "PYTHONUTF8=1"

if defined CLAUDE_CODE_GIT_BASH_PATH for %%I in ("%CLAUDE_CODE_GIT_BASH_PATH%") do if /i "%%~xI"==".exe" (
  "%%~I" "%~dp0forge" --help >nul 2>nul
  if not errorlevel 1 set "FORGE_SH=%%~I"
)
if defined FORGE_SH goto run_sh

for /f "delims=" %%I in ('where sh 2^>nul') do if not defined FORGE_SH for %%J in ("%%I") do if /i "%%~xJ"==".exe" (
  "%%~J" "%~dp0forge" --help >nul 2>nul
  if not errorlevel 1 set "FORGE_SH=%%~J"
)
if defined FORGE_SH goto run_sh

for %%I in (
  "%ProgramFiles%\Git\bin\bash.exe"
  "%ProgramFiles%\Git\usr\bin\bash.exe"
  "%ProgramFiles%\Git\usr\bin\sh.exe"
  "%ProgramFiles(x86)%\Git\bin\bash.exe"
  "%ProgramFiles(x86)%\Git\usr\bin\bash.exe"
  "%ProgramFiles(x86)%\Git\usr\bin\sh.exe"
  "%LOCALAPPDATA%\Programs\Git\bin\bash.exe"
  "%LOCALAPPDATA%\Programs\Git\usr\bin\bash.exe"
  "%LOCALAPPDATA%\Programs\Git\usr\bin\sh.exe"
) do if not defined FORGE_SH if exist "%%~I" if /i "%%~xI"==".exe" (
  "%%~I" "%~dp0forge" --help >nul 2>nul
  if not errorlevel 1 set "FORGE_SH=%%~I"
)
if defined FORGE_SH goto run_sh
goto python

:run_sh
"%FORGE_SH%" "%~dp0forge" %*
exit /b %errorlevel%

:python
where py >nul 2>nul
if errorlevel 1 goto python_fallback
py -3 -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>nul
if errorlevel 1 goto python_fallback
py -3 "%~dp0factory\scripts\forge.py" %*
exit /b %errorlevel%

:python_fallback
where python >nul 2>nul
if errorlevel 1 goto missing
python -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>nul
if errorlevel 1 goto missing
python "%~dp0factory\scripts\forge.py" %*
exit /b %errorlevel%

:missing
echo [FAIL] Git Bash or Python 3.10 or newer was not found. 1>&2
exit /b 2
