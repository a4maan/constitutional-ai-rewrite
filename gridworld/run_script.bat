@echo off
setlocal EnableExtensions EnableDelayedExpansion

set "ROOT_DIR=%~dp0"
if "%ROOT_DIR:~-1%"=="\" set "ROOT_DIR=%ROOT_DIR:~0,-1%"
set "SCRIPTS_DIR=%ROOT_DIR%\scripts"
set "VENV_DIR=%ROOT_DIR%\.venv"
set "REQUIREMENTS_FILE=%ROOT_DIR%\requirements.txt"

if defined PYTHON_BIN (
  set "PYTHON_CMD=%PYTHON_BIN%"
) else (
  set "PYTHON_CMD=python"
)

if not exist "%SCRIPTS_DIR%" (
  echo error: scripts directory "%SCRIPTS_DIR%" does not exist 1>&2
  exit /b 1
)

set "script_count=0"
for /f "delims=" %%F in ('dir /b /a:-d "%SCRIPTS_DIR%\*.py" 2^>nul') do (
  set /a script_count+=1
  set "script_path[!script_count!]=%SCRIPTS_DIR%\%%F"
)

if "!script_count!"=="0" (
  echo No Python scripts found in "%SCRIPTS_DIR%" 1>&2
  exit /b 1
)

echo Available scripts:
for /l %%I in (1,1,!script_count!) do (
  set "script=!script_path[%%I]!"
  set "rel_script=!script:%ROOT_DIR%\=!"
  if "!rel_script!"=="" set "rel_script=!script!"
  echo   %%I) !rel_script!
)
echo.

set "selection="
set /p selection=Select a script to run [1-!script_count!^]: 

echo.
if not defined selection (
  echo error: selection is required 1>&2
  exit /b 1
)

echo(!selection!|findstr /r "^[0-9][0-9]*$" >nul
if errorlevel 1 (
  echo error: selection must be an integer between 1 and !script_count! 1>&2
  exit /b 1
)

set /a selection_int=%selection%
if %selection_int% lss 1 (
  echo error: selection must be at least 1 1>&2
  exit /b 1
)
if %selection_int% gtr !script_count! (
  echo error: selection cannot exceed !script_count! 1>&2
  exit /b 1
)

call set "selected_script=%%script_path[%selection_int%]%%"
if not defined selected_script (
  echo error: unable to determine script for selection %selection_int% 1>&2
  exit /b 1
)

set "USER_ARGS="
set /p USER_ARGS=Enter arguments (space-delimited, optional^): 
echo.

where "%PYTHON_CMD%" >nul 2>nul
if errorlevel 1 (
  if not exist "%PYTHON_CMD%" (
    echo error: cannot find python interpreter "%PYTHON_CMD%" in PATH 1>&2
    exit /b 1
  )
)

if not exist "%VENV_DIR%" (
  echo Creating virtual environment in "%VENV_DIR%"
  "%PYTHON_CMD%" -m venv "%VENV_DIR%"
  if errorlevel 1 exit /b 1
)

if not exist "%VENV_DIR%\Scripts\activate.bat" (
  echo error: virtual environment activation script not found in "%VENV_DIR%\Scripts" 1>&2
  exit /b 1
)

call "%VENV_DIR%\Scripts\activate.bat"

"%VENV_DIR%\Scripts\python.exe" -m pip install --upgrade pip setuptools wheel
if errorlevel 1 exit /b 1

if exist "%REQUIREMENTS_FILE%" (
  pip install -r "%REQUIREMENTS_FILE%"
  if errorlevel 1 exit /b 1
)

if defined PYTHONPATH (
  set "PYTHONPATH=%ROOT_DIR%\src;%PYTHONPATH%"
) else (
  set "PYTHONPATH=%ROOT_DIR%\src"
)
set "PYTHONUNBUFFERED=1"

set "display_script=%selected_script%"
set "display_script=%display_script:%ROOT_DIR%\=%"
if "%display_script%"=="" set "display_script=%selected_script%"
echo Running %display_script%

"%VENV_DIR%\Scripts\python.exe" "%selected_script%" %USER_ARGS%
set "exit_code=%errorlevel%"

endlocal & exit /b %exit_code%

