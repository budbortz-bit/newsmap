@echo off
cd /d "C:\Users\budbo\OneDrive\Documents\newsmap"
call venv\Scripts\activate.bat
python main.py
timeout /t 10
exit