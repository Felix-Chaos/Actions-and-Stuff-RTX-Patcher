@echo off
setlocal enabledelayedexpansion
title Actions & Stuff RTX Patcher V3 - Release Builder

echo =================================================================
echo   ACTIONS & STUFF RTX PATCHER V3 - RELEASE BUILDER
echo =================================================================
echo.

:: Get current version from tauri.conf.json
for /f "usebackq tokens=*" %%i in (`powershell -NoProfile -Command "(Get-Content src-tauri/tauri.conf.json -Raw | ConvertFrom-Json).version"`) do (
    set "CURRENT_VERSION=%%i"
)

echo Current Version: !CURRENT_VERSION!
echo.
set /p "NEW_VERSION=Enter new version number (press Enter to keep !CURRENT_VERSION!): "
if "!NEW_VERSION!"=="" (
    set "NEW_VERSION=!CURRENT_VERSION!"
)

echo.
echo [1/3] Updating configuration files to version !NEW_VERSION!...
powershell -NoProfile -Command ^
    "$conf = Get-Content src-tauri/tauri.conf.json -Raw | ConvertFrom-Json; ^
     $conf.version = '!NEW_VERSION!'; ^
     $conf | ConvertTo-Json -Depth 20 | Set-Content src-tauri/tauri.conf.json; ^
     $pkg = Get-Content package.json -Raw | ConvertFrom-Json; ^
     $pkg.version = '!NEW_VERSION!'; ^
     $pkg | ConvertTo-Json -Depth 20 | Set-Content package.json; ^
     Write-Host 'Config files updated successfully!' -ForegroundColor Green"

echo.
echo [2/3] Building production package (npm run tauri build)...
echo This might take several minutes depending on your CPU. Please wait...
echo.
call npm run tauri build

if %ERRORLEVEL% neq 0 (
    echo.
    echo [ERROR] Tauri build failed!
    pause
    exit /b %ERRORLEVEL%
)

echo.
echo [3/3] Locating build outputs...
set "BUNDLE_DIR=src-tauri\target\release\bundle"
if exist "!BUNDLE_DIR!" (
    echo.
    echo Build completed successfully! Opening bundle directory:
    echo   !BUNDLE_DIR!
    echo.
    explorer "!BUNDLE_DIR!"
) else (
    echo.
    echo Build directory not found. Please check src-tauri/target/release/
)

echo.
echo All tasks finished.
pause
