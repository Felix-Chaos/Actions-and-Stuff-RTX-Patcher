@ECHO OFF
TITLE A.n.S RTX Patcher Build System
SETLOCAL ENABLEDELAYEDEXPANSION

:: Set a fixed hash seed for deterministic builds
SET PYTHONHASHSEED=0

:: --- Configuration ---
SET SCRIPT_NAME=main.py
SET ICON_NAME=assets\resources\icon.ico
SET OUTPUT_NAME=AnS_RTX_Patcher_V2.exe
SET DIST_FOLDER=dist

:: --- Dependency Check ---
:check_deps
CLS
ECHO --------------------------------------
ECHO      Dependency Check
ECHO --------------------------------------
ECHO.
SET MISSING_DEPS=0

:: Check PyInstaller
py -c "import PyInstaller" >NUL 2>&1
IF %ERRORLEVEL% NEQ 0 (
    ECHO [X] PyInstaller is MISSING.
    SET MISSING_DEPS=1
) ELSE (
    ECHO [OK] PyInstaller found.
)

:: Check Pillow
py -c "import PIL" >NUL 2>&1
IF %ERRORLEVEL% NEQ 0 (
    ECHO [X] Pillow - PIL is MISSING.
    SET MISSING_DEPS=1
) ELSE (
    ECHO [OK] Pillow found.
)

:: Check ttkbootstrap
py -c "import ttkbootstrap" >NUL 2>&1
IF %ERRORLEVEL% NEQ 0 (
    ECHO [X] ttkbootstrap is MISSING.
    SET MISSING_DEPS=1
) ELSE (
    ECHO [OK] ttkbootstrap found.
)

ECHO.
IF !MISSING_DEPS! EQU 1 (
    ECHO Some dependencies are missing.
    CHOICE /C YN /M "Do you want to attempt auto-installation?"
    IF !ERRORLEVEL! EQU 1 (
        ECHO.
        ECHO Installing dependencies...
        py -m pip install pypiwin32 pyinstaller pillow ttkbootstrap
        ECHO.
        ECHO Installation attempt complete. Re-checking...
        PAUSE
        GOTO :check_deps
    ) ELSE (
        ECHO Warning: Build may fail without dependencies.
        PAUSE
    )
) ELSE (
    ECHO All dependencies look good!
)

:: --- Main Menu ---
:menu
CLS
ECHO ######################################
ECHO #    A.n.S RTX Patcher Build Menu    #
ECHO ######################################
ECHO.
ECHO    [1] BUILD - Release (Windowed, No Console)
ECHO    [2] BUILD - Debug (Console Enabled)
ECHO    [3] UTILS - Update Version Number (Bump Patch)
ECHO    [4] UTILS - Clean Build Files
ECHO    [5] EXIT
ECHO.
CHOICE /C 12345 /M "Select an option:"

IF %ERRORLEVEL%==1 GOTO :build_release
IF %ERRORLEVEL%==2 GOTO :build_debug
IF %ERRORLEVEL%==3 GOTO :bump_version
IF %ERRORLEVEL%==4 GOTO :clean
IF %ERRORLEVEL%==5 GOTO :eof

:: --- Build Logic ---
:build_release
SET CONSOLE_FLAG=--windowed
SET BUILD_TYPE=Release
GOTO :do_build

:build_debug
SET CONSOLE_FLAG=--console
SET BUILD_TYPE=Debug
GOTO :do_build

:do_build
CLS
ECHO.
ECHO ==========================================
ECHO   Building %BUILD_TYPE% Version...
ECHO ==========================================
ECHO.

py -m PyInstaller --onefile %CONSOLE_FLAG% --name "%OUTPUT_NAME%" --icon="%ICON_NAME%" ^
--add-data "assets;assets" ^
--add-data "tools;tools" ^
"%SCRIPT_NAME%"

ECHO.
IF EXIST "%DIST_FOLDER%\\%OUTPUT_NAME%" (
    ECHO SUCCESS: Build complete!
    ECHO Location: %CD%\%DIST_FOLDER%\%OUTPUT_NAME%
    ECHO.
    CHOICE /C YN /M "Check executable in folder?"
    IF !ERRORLEVEL! EQU 1 (
        explorer "%DIST_FOLDER%"
    )
) ELSE (
    ECHO ERROR: Build failed. Check the output above.
)
PAUSE
GOTO :menu

:: --- Utilities ---
:bump_version
ECHO.
py tools/version_bumper.py
PAUSE
GOTO :menu

:clean
ECHO.
ECHO Cleaning up temporary files (build/, dist/, .spec)...
IF EXIST "build" ( RMDIR /S /Q build )
IF EXIST "dist" ( RMDIR /S /Q dist )
IF EXIST "*.spec" ( DEL "*.spec" )
ECHO Done.
PAUSE
GOTO :menu

:eof
EXIT
