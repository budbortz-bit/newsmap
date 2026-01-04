@echo off
:: Navigate to the folder
cd /d "C:\Users\budbo\OneDrive\Documents\newsmap"

:: 1. GENERATE THE SITE
call venv\Scripts\activate.bat
python main.py

:: 2. UPLOAD TO GITHUB
:: Stage the new image and HTML
git add .

:: Save it with today's date
git commit -m "Daily NewsMap Update: %date%"

:: Push it to the live website
git push origin main

:: Keep window open for 10 seconds so you can see if it worked
timeout /t 10
exit