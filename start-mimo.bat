@echo off
cd /d "%~dp0"
echo Starting API Bridge (Xiaomi Mimo)...
start "API Bridge" python server.py
timeout /t 2 >nul
set ANTHROPIC_BASE_URL=http://localhost:4000
set ANTHROPIC_AUTH_TOKEN=*** ANTHROPIC_MODEL=mimo-v2.5-pro[1m]
cd /d "E:\claude-code专用文件夹"
claude
