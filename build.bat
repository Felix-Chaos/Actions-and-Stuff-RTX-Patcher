@ECHO OFF
TITLE A.n.S RTX Patcher Build Script
SETLOCAL ENABLEDELAYEDEXPANSION

:: Set a fixed hash seed for deterministic builds
SET PYTHONHASHSEED=0

:: --- Configuration ---
SET SCRIPT_NAME=main.py
SET ICON_NAME=assets\resources\icon.ico
SET OUTPUT_NAME=AnS_RTX_Patcher_V2.exe
SET DIST_FOLDER=dist

:: --- Pre-build Checks ---
CLS
ECHO ######################################
ECHO #    A.n.S RTX Patcher Build Script    #
ECHO ######################################
ECHO.
ECHO Checking file structure...
IF NOT EXIST "%SCRIPT_NAME%" (
    ECHO ERROR: Main script '%SCRIPT_NAME%' not found!
    GOTO :error
)
IF NOT EXIST "%ICON_NAME%" (
    ECHO ERROR: Icon '%ICON_NAME%' not found!
    GOTO :error
)
IF NOT EXIST "tools" (
    ECHO WARNING: 'tools' directory not found. Creator tools will be missing.
)
ECHO File structure looks OK.
ECHO.
ECHO This script will build the patcher into a standalone .exe file.
ECHO The final executable will be in the '%DIST_FOLDER%' folder.
PAUSE
ECHO.

:: --- Auto-Increment Version ---
ECHO.
ECHO Updating version...
py tools/version_bumper.py

:: --- Starting Build ---
ECHO.
ECHO Running PyInstaller...

py -m PyInstaller --onefile --windowed --name "%OUTPUT_NAME%" --icon="%ICON_NAME%" ^
--add-data "assets;assets" ^
--add-data "tools;tools" ^
"%SCRIPT_NAME%"

:: --- Post-build Checks & Cleanup ---
ECHO.
IF EXIST "%DIST_FOLDER%\\%OUTPUT_NAME%" (
    ECHO SUCCESS: Build complete! Find the executable in the '%DIST_FOLDER%' folder.
) ELSE (
    ECHO ERROR: Build failed. Check the output above for errors.
    GOTO :error
)
ECHO.

CHOICE /C YN /M "Do you want to clean up temporary build files (build folder and .spec file)?"
IF %ERRORLEVEL%==1 (
    ECHO.
    ECHO Cleaning up temporary files...
    IF EXIST "build" ( RMDIR /S /Q build )
    IF EXIST "*.spec" ( DEL "*.spec" )
    ECHO Cleanup complete.
)

GOTO :end

:error
ECHO.
ECHO Build failed. Please review the error messages.

:end
ECHO.
ECHO Build process finished.
PAUSE
