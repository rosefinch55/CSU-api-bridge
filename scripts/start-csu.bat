@echo off
cd /d "%~dp0"
echo Starting API Bridge (CSU)...
start "API Bridge" python ../server.py
ping -n 3 127.0.0.1 >nul
set ANTHROPIC_BASE_URL=http://localhost:4000
set ANTHROPIC_AUTH_TOKEN=sk-xaBFFevDMTyUMiC94LMrpuJ3wq4ftvHjtJcFoxkdBjtkvT2m
set ANTHROPIC_MODEL=csu-deepseek-thinking[1m]
cd /d "E:\claude-code专用文件夹"
claude --enable-auto-mode
