@echo off
title Crypto Bot — Dashboard
color 0B

echo ============================================
echo  CRYPTO BOT — DASHBOARD
echo ============================================
echo.
echo  Mo browser: http://localhost:8501
echo  De tat: dong cua so nay hoac nhan Ctrl+C
echo ============================================
echo.

cd /d "%~dp0"

if not exist "dashboard.py" (
    echo [LOI] Khong tim thay dashboard.py!
    pause
    exit /b 1
)

:: Mở browser tự động sau 3 giây
start "" timeout /t 3 /nobreak >nul
start "" "http://localhost:8501"

:: Chạy Streamlit
streamlit run dashboard.py --server.port 8501

pause
