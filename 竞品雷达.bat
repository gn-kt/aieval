@echo off
chcp 65001 >nul
cd /d D:\codebase\作品集\竞品雷达
title 竞品雷达
echo ============================
echo  竞品雷达 启动中...
echo ============================

echo [1/4] 清理旧进程...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8000.*LISTENING"') do taskkill /f /pid %%a >nul 2>&1
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":5173.*LISTENING"') do taskkill /f /pid %%a >nul 2>&1
taskkill /f /fi "IMAGENAME eq python.exe" /fi "WINDOWTITLE eq *celery*" >nul 2>&1
for /d /r . %%d in (__pycache__) do @if exist "%%d" rd /s /q "%%d" 2>nul

echo [2/4] 启动 Redis...
taskkill /f /im redis-server.exe >nul 2>&1
start /min "" "D:\IT_environment\Redis\redis-server.exe"
timeout /t 2 >nul

echo [3/4] 启动服务（前台运行 Ctrl+C 即停）...
echo.
echo   Celery    → 后台窗口
echo   FastAPI   → 后台窗口
echo   Vite      → 后台窗口
echo.

start "Celery" /min cmd /c "cd /d D:\codebase\作品集\竞品雷达 && D:\IT_environment\Miniconda3\envs\ai_agent\python.exe -m celery -A celery_app worker --loglevel=warning --pool=solo --concurrency=1"
start "FastAPI" /min cmd /c "cd /d D:\codebase\作品集\竞品雷达 && D:\IT_environment\Miniconda3\envs\ai_agent\python.exe -m uvicorn api:app --host 0.0.0.0 --port 8000"
start "Vite" /min cmd /c "set PATH=D:\IT_environment\Nvm\nodejs;D:\IT_environment\Nvm\nodejs\node_modules\.bin;%PATH% && cd /d D:\codebase\作品集\竞品雷达\frontend && D:\IT_environment\Nvm\nodejs\npm.cmd run dev"

echo 等待就绪 (15s)...
timeout /t 15 >nul

curl -s http://127.0.0.1:8000/health >nul 2>&1
if errorlevel 1 (
    echo [错误] FastAPI 启动失败! 请检查日志窗口.
    pause
    exit /b 1
)

echo.
echo ============================
echo  启动完成! http://localhost:5173
echo ============================
echo  Ctrl+C 关闭所有服务
echo ============================
start http://localhost:5173

:wait
timeout /t 5 >nul
goto wait
