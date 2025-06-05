@echo off
echo Starting DCS AI Copilot System...

REM --- Start TelemetryApp.exe in a new window ---
echo Launching Telemetry App...
start "" ".\Server\TelemetryApp.exe.lnk"

REM --- Activate Python venv and run copilot script ---
echo Launching Copilot AI script...
call dcs_ollama\Scripts\activate.bat
python dcs_copilot_main.py

REM Optional: Echo instructions for running manually
echo.
echo To run manually next time:
echo   CALL .\Server\TelemetryApp.exe.lnk
echo   call dcs_ollama\Scripts\activate.bat
echo   python dcs_copilot_main.py
pause
