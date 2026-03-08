@echo off
cd /d "%~dp0"
title Harun AI Bot

:BASLAT
echo.
echo ========================================
echo   HARUN AI BOT BASLATILIYOR...
echo ========================================
echo.

REM --- Aşama 21 Enterprise Test Modu (Gate eşiği) ---
REM 50 beklememek için 5'e düşürür. İstersen 50 yapabilirsin.
set EGITIM_REVIEW_BATCH=5
REM --- /Aşama 21 Enterprise Test Modu ---

python telegram_bot.py

echo.
echo Bot durdu! 5 saniye sonra yeniden baslatiliyor...
echo Tamamen kapatmak icin Ctrl+C basin.
echo.
timeout /t 5
goto BASLAT
