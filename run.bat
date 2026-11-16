@echo off
setlocal
pushd "%~dp0" || exit /b 2
where py >nul 2>&1
if not errorlevel 1 (
  py -3.12 -B -c "import sys, tkinter; assert sys.version_info[:2] == (3, 12)" >nul 2>&1
  if not errorlevel 1 (
    set "NEURAL_PY=py -3.12"
    goto ready
  )
)
where python >nul 2>&1
if not errorlevel 1 (
  python -B -c "import sys, tkinter; assert sys.version_info[:2] == (3, 12)" >nul 2>&1
  if not errorlevel 1 (
    set "NEURAL_PY=python"
    goto ready
  )
)
echo Neural Office requires Python 3.12 with Tk. Install it and try again.
popd
if "%~1"=="" pause
exit /b 2
:ready
if "%~1"=="" (
  %NEURAL_PY% -B -m neural_office gui
) else (
  %NEURAL_PY% -B -m neural_office %*
)
set "NEURAL_RESULT=%ERRORLEVEL%"
popd
if not "%NEURAL_RESULT%"=="0" if "%~1"=="" pause
exit /b %NEURAL_RESULT%
