@ECHO OFF
SETLOCAL EnableExtensions
TITLE AnS RTX Patcher Build Script

REM --- CONFIGURATION ---
SET SCRIPT_NAME=AnS_RTX_Universial_Patcher.py
SET ICON_FILE=AnSPatchericon.ico
SET PATCHER_EXEC=xdelta3\exec\xdelta3_x86_64_win.exe
SET MANIFEST_FILE=xdelta3\manifest\manifest.json

REM --- PRE-CHECK: PYTHON ---
WHERE python >NUL 2>NUL
IF ERRORLEVEL 1 (
    ECHO ERROR: Python is not installed or not in PATH!
    ECHO Please install Python from https://www.python.org/downloads/
    PAUSE
    EXIT /B 1
)

REM --- PRE-CHECK: PIP ---
python -m pip --version >NUL 2>NUL
IF ERRORLEVEL 1 (
    ECHO Pip is not installed. Trying to install...
    python -m ensurepip --upgrade
    IF ERRORLEVEL 1 (
        ECHO ERROR: Pip could not be installed.
        PAUSE
        EXIT /B 1
    )
)

REM --- PRE-CHECK: PYINSTALLER ---
python -m pip show pyinstaller >NUL 2>NUL
IF ERRORLEVEL 1 (
    ECHO PyInstaller not found. Installing...
    python -m pip install --upgrade pip
    python -m pip install pyinstaller
    IF ERRORLEVEL 1 (
        ECHO ERROR: Failed to install PyInstaller!
        PAUSE
        EXIT /B 1
    )
)

REM --- PRE-CHECK: FILE STRUCTURE ---
IF NOT EXIST "%SCRIPT_NAME%" (
    ECHO ERROR: Script '%SCRIPT_NAME%' not found!
    PAUSE
    EXIT /B 1
)
IF NOT EXIST "%ICON_FILE%" (
    ECHO ERROR: Icon file '%ICON_FILE%' not found!
    PAUSE
    EXIT /B 1
)
IF NOT EXIST "%PATCHER_EXEC%" (
    ECHO ERROR: Patcher '%PATCHER_EXEC%' not found!
    PAUSE
    EXIT /B 1
)
IF NOT EXIST "%MANIFEST_FILE%" (
    ECHO ERROR: Manifest '%MANIFEST_FILE%' not found!
    PAUSE
    EXIT /B 1
)

ECHO All dependencies are present.
ECHO Building standalone executable...

REM --- BUILD ---
python -m PyInstaller --onefile --windowed ^
--icon="%ICON_FILE%" ^
--add-data "xdelta3/exec;xdelta3/exec" ^
--add-data "xdelta3/manifest;xdelta3/manifest" ^
--add-data "%ICON_FILE%;." ^
"%SCRIPT_NAME%"

REM --- RESULT ---
SET "EXE_FILE=dist\%SCRIPT_NAME:.py=.exe%"
IF EXIST "%EXE_FILE%" (
    ECHO Success! Your executable "%EXE_FILE%" was created.
) ELSE (
    ECHO ERROR: Build failed. Please check the output above for details.
)

REM --- OPTIONAL: CLEAN UP ---
CHOICE /C YN /M "Do you want to clean up temporary build files (the 'build' folder and .spec file)?"
IF ERRORLEVEL 1 (
    ECHO Cleaning up...
    IF EXIST "build" (RMDIR /S /Q build)
    IF EXIST "%SCRIPT_NAME:.py=.spec%" (DEL "%SCRIPT_NAME:.py=.spec%")
    ECHO Cleanup complete.
)

ECHO Done.
PAUSE

ENDLOCAL
