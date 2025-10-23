@echo off
title Building AnS RTX Patcher...

:: Clean previous builds
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist AnSRTXPatcher.spec del AnSRTXPatcher.spec

:: Run PyInstaller with custom icon and data files
pyinstaller --noconsole --onefile AnSRTXPatcher.py ^
--icon=AnSPatchericon.ico ^
--add-data "AnSPatchericon.png;." ^
--add-data "xdelta3;./xdelta3"

echo.
echo ✅ Build complete!
echo The executable is located in the /dist folder.
pause
