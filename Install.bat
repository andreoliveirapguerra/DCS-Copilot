@echo off
echo Creating virtual environment...
@REM call Python.exe -m venv dcs_ollama

echo Activating virtual environment...
call dcs_ollama\Scripts\activate.bat

echo Installing required Python packages...
call dcs_ollama\Scripts\Python.exe -m pip install -r requirements.txt

echo.
echo ✅ Environment setup complete. To activate later, run:
echo call dcs_ollama\Scripts\activate.bat
pause