@ECHO OFF
TITLE AnS RTX Patcher Build Script

:: --- Configuration ---
:: !!! IMPORTANT: Change this to the name of your Python script !!!
SET SCRIPT_NAME=AnSRTXPatcher.py

:: --- Script Start ---
CLS
ECHO ###################################
ECHO # AnS RTX Patcher Build Script    #
ECHO ###################################
ECHO.

:: --- Pre-build Checks ---
ECHO Checking file structure...
IF NOT EXIST "%SCRIPT_NAME%" (
    ECHO ERROR: Script '%SCRIPT_NAME%' not found!
    GOTO :error
)
IF NOT EXIST "AnSPatchericon.ico" (
    ECHO ERROR: Icon file 'AnSPatchericon.ico' not found!
    GOTO :error
)
IF NOT EXIST "xdelta3\exec\xdelta3_x86_64_win.exe" (
    ECHO ERROR: Patcher 'xdelta3\exec\xdelta3_x86_64_win.exe' not found!
    GOTO :error
)
IF NOT EXIST "xdelta3\manifest\manifest.json" (
    ECHO ERROR: Manifest 'xdelta3\manifest\manifest.json' not found!
    GOTO :error
)
ECHO File structure looks OK.
ECHO.
ECHO This script will build %SCRIPT_NAME% into a standalone .exe file.
ECHO The final .exe will be located in a new 'dist' folder.
PAUSE

ECHO.
ECHO --- Starting Build ---
ECHO.

:: Build command - More specific about what data to add
pyinstaller --onefile --windowed --icon="AnSPatchericon.ico" ^
--add-data "xdelta3/exec;xdelta3/exec" ^
--add-data "xdelta3/manifest;xdelta3/manifest" ^
--add-data "AnSPatchericon.ico;." ^
%SCRIPT_NAME%

ECHO.
ECHO --- Build Finished ---
ECHO.

IF EXIST "dist\%SCRIPT_NAME:.py=.exe%" (
    ECHO SUCCESS: Your .exe file has been created in the 'dist' folder.
) ELSE (
    ECHO ERROR: The build process failed. Please check the output above for errors.
)

ECHO.
CHOICE /C YN /M "Do you want to clean up temporary build files (build folder and .spec file)?"

IF %ERRORLEVEL%==1 (
    ECHO.
    ECHO Cleaning up temporary files...
    IF EXIST "build" ( RMDIR /S /Q build )
    IF EXIST "%SCRIPT_NAME:.py=.spec%" ( DEL "%SCRIPT_NAME:.py=.spec%" )
    ECHO Cleanup complete.
)
GOTO :end

:error
ECHO.
ECHO Build failed due to missing files.
ECHO Please make sure your folder structure is correct and all required files are present.
ECHO.

:end
ECHO Build process finished.
PAUSE

