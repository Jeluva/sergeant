@echo off
chcp 65001 >nul
title SERGEANT - DEMO LAUNCHER
cd /d "%~dp0"
echo.
echo  ==========================================
echo   SERGEANT v1.0  //  ANTIhackaton demo
echo  ==========================================
echo.
echo  COMO FUNCIONA:
echo    - Abre apps de distraccion (YouTube, Twitter, etc.)
echo    - 3 infracciones: cierre automatico de pestana
echo    - 4ta infraccion: countdown fake sys32 deletion
echo    - Retoma trabajo: countdown PAUSA
echo    - Vuelves a distraerte: countdown REANUDA
echo.
echo  PARA EL DEMO:
echo    - Cambia objetivo: tab MISION en el dashboard
echo    - Vincula Twitter: tab TWITTER en el dashboard
echo    - Ctrl+D en el dashboard = fuerza countdown demo
echo.
echo  Presiona cualquier tecla para lanzar...
pause >nul
python sergeant\main.py
pause
