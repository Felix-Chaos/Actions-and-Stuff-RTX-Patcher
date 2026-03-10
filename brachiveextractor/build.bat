@echo off
echo Building Brarchive Extractor...
pyinstaller --noconfirm --onefile --windowed --name "Brarchive Extractor" main.py
echo Build Complete!
pause
