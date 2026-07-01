@echo off
chcp 65001 >nul
title SERGEANT - DEMO LAUNCHER
cd /d "%~dp0"
echo.
echo  ==========================================
echo   SERGEANT v1.0  //  ANTIhackaton demo
echo  ==========================================
echo.
python sergeant\main.py
