@echo off
cd /d "%~dp0"
echo Vedant Swing — Validate past predictions vs actual prices
python model_audit.py
pause
