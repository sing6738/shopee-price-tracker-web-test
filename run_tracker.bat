@echo off
chcp 65001 > nul
title Shopee Price Tracker

set CLOUD_URL=https://shopee-tracker-7d91.onrender.com
set TRACKER_API_KEY=ShopeeKey99

echo ============================================
echo   Shopee Price Tracker - Cloud Push
echo   %date% %time%
echo ============================================
echo.

cd /d "%~dp0"

if not exist "%~dp0shopee_cookies.json" (
    echo ไม่พบ shopee_cookies.json
    echo กรุณารัน: python loginshopee.py ก่อน
    pause
    exit /b 1
)

python tracker_cloud.py

echo.
echo ============================================
echo   Done: %date% %time%
echo ============================================
timeout /t 5 /nobreak > nul
