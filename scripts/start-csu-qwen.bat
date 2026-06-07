@echo off
cd /d "%~dp0"
echo Starting API Bridge (CSU Qwen)...
start "API Bridge" python server.py
timeout /t 2 >nul
set ANTHROPIC_BASE_URL=http://localhost:4000
set ANTHROPIC_AUTH_TOKEN=%CSU_KEY%
set ANTHROPIC_MODEL=csu-qwen[256k]
cd /d "E:\claude-codeר���ļ���"
claude --enable-auto-mode