@echo off
title Crypto Bot — Running (Schedule Mode)
color 0A

echo ============================================
echo  CRYPTO BOT — CHE DO TU DONG
echo ============================================
echo.
echo  BTC report  : moi 24h
echo  BTC alert   : moi 1h
echo  Alt scan    : moi 6h
echo.
echo  De tat bot: dong cua so nay hoac nhan Ctrl+C
echo ============================================
echo.

:: Chuyển vào folder chứa bot (tự động lấy đúng path)
cd /d "%~dp0"

:: Kiểm tra Python có không
python --version >nul 2>&1
if errorlevel 1 (
    echo [LOI] Khong tim thay Python!
    echo Tai Python tai: https://www.python.org/downloads/
    pause
    exit /b 1
)

:: Kiểm tra main.py có không
if not exist "main.py" (
    echo [LOI] Khong tim thay main.py!
    echo Chac chan ban dang chay file .bat nay trong dung folder chua bot.
    pause
    exit /b 1
)

echo [OK] Khoi dong bot...
echo.

:: Chạy bot ở chế độ schedule
python main.py --schedule

:: Nếu bot crash → tự restart sau 10 giây
echo.
echo [!] Bot bi dung. Tu khoi dong lai sau 10 giay...
timeout /t 10 /nobreak
goto :eof
