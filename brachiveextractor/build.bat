@echo off
echo Building Brarchive Extractor...
pyinstaller --noconfirm --onedir --windowed --name "Brarchive Extractor" main.py
echo Build Complete!
pause
