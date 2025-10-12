@ECHO OFF
SETLOCAL ENABLEDELAYEDEXPANSION
TITLE AnS RTX Patcher - Automated Build Script
CLS

:: =========================================================
:: CONFIGURATION
:: =========================================================
SET SCRIPT_NAME=AnS_RTX_Patcher.py
SET ICON_FILE=AnSPatchericon.ico
SET PYTHON_EXE=python
SET PYINSTALLER_ARGS=--onefile --windowed --icon="%ICON_FILE%" ^
 --add-data "xdelta3/exec;xdelta3/exec" ^
 --add-data "xdelta3/manifest;xdelta3/manifest" ^
 --add-data "%ICON_FILE%;." ^
 %SCRIPT_NAME%

ECHO ###############################################
ECHO #   AnS RTX Patcher - Automated Build Script   #
ECHO ###############################################
ECHO.

:: =========================================================
:: STEP 1 - CHECK PYTHON INSTALLATION
:: =========================================================
ECHO Checking Python installation...
%PYTHON_EXE% --version >NUL 2>&1
IF ERRORLEVEL 1 (
    ECHO ERROR: Python is not installed or not in PATH.
    ECHO Please install Python 3.11+ and re-run this script.
    PAUSE
    EXIT /B 1
)
FOR /F "tokens=2 delims= " %%A IN ('%PYTHON_EXE% --version 2^>^&1') DO SET PY_VER=%%A
ECHO Found Python version: %PY_VER%
ECHO.

:: =========================================================
:: STEP 2 - CHECK AND INSTALL DEPENDENCIES
:: =========================================================
ECHO Checking dependencies...
SET NEED_INSTALL=0

:: Check ttkbootstrap
%PYTHON_EXE% -m pip show ttkbootstrap >NUL 2>&1
IF ERRORLEVEL 1 (
    ECHO ttkbootstrap not found. Installing...
    %PYTHON_EXE% -m pip install git+https://github.com/israel-dryer/ttkbootstrap
    SET NEED_INSTALL=1
)

:: Check PyInstaller
%PYTHON_EXE% -m pip show pyinstaller >NUL 2>&1
IF ERRORLEVEL 1 (
    ECHO PyInstaller not found. Installing...
    %PYTHON_EXE% -m pip install pyinstaller
    SET NEED_INSTALL=1
)

IF %NEED_INSTALL%==0 (
    ECHO All dependencies are already installed.
)
ECHO.

:: =========================================================
:: STEP 3 - VERIFY FILE STRUCTURE
:: =========================================================
ECHO Checking project structure...
IF NOT EXIST "%SCRIPT_NAME%" (
    ECHO ERROR: Script '%SCRIPT_NAME%' not found.
    GOTO :error
)
IF NOT EXIST "%ICON_FILE%" (
    ECHO ERROR: Icon file '%ICON_FILE%' not found.
    GOTO :error
)
IF NOT EXIST "xdelta3\exec\xdelta3_x86_64_win.exe" (
    ECHO ERROR: Missing xdelta3 executable at xdelta3\exec\xdelta3_x86_64_win.exe
    GOTO :error
)
IF NOT EXIST "xdelta3\manifest\manifest.json" (
    ECHO ERROR: Missing manifest at xdelta3\manifest\manifest.json
    GOTO :error
)
ECHO File structure OK.
ECHO.

:: =========================================================
:: STEP 4 - START BUILD PROCESS
:: =========================================================
ECHO Starting build with PyInstaller...
%PYTHON_EXE% -m PyInstaller %PYINSTALLER_ARGS%

IF ERRORLEVEL 1 (
    ECHO.
    ECHO ERROR: Build process failed. Check error messages above.
    GOTO :end
)

:: =========================================================
:: STEP 5 - POST-BUILD VERIFICATION
:: =========================================================
ECHO.
IF EXIST "dist\%SCRIPT_NAME:.py=.exe%" (
    ECHO SUCCESS: Build completed successfully.
    ECHO Output file: dist\%SCRIPT_NAME:.py=.exe%
) ELSE (
    ECHO ERROR: The .exe file was not created. Check PyInstaller output.
)
ECHO.

:: =========================================================
:: STEP 6 - CLEANUP PROMPT
:: =========================================================
CHOICE /C YN /M "Do you want to remove temporary build files (build folder + .spec file)?"
IF %ERRORLEVEL%==1 (
    ECHO Cleaning up temporary files...
    IF EXIST "build" RMDIR /S /Q build
    IF EXIST "%SCRIPT_NAME:.py=.spec%" DEL "%SCRIPT_NAME:.py=.spec%"
    ECHO Cleanup complete.
)
GOTO :end

:error
ECHO.
ECHO Build aborted due to missing files or invalid setup.
ECHO Verify your folder structure and try again.
ECHO.

:end
ECHO Build process finished.
PAUSE
ENDLOCAL
