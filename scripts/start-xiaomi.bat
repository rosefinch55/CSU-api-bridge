@echo off
cd /d "%~dp0"
echo Starting API Bridge (Xiaomi)...
set ANTHROPIC_BASE_URL=https://token-plan-cn.xiaomimimo.com/anthropic
set ANTHROPIC_AUTH_TOKEN=%MIMO_KEY%
set ANTHROPIC_MODEL=mimo-v2.5[1m]
cd /d "E:\claude-codeר���ļ���"
claude --enable-auto-mode
