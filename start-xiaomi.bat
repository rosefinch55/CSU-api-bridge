@echo off
cd /d "%~dp0"
echo Starting API Bridge (Xiaomi)...
set ANTHROPIC_BASE_URL=https://token-plan-cn.xiaomimimo.com/anthropic
set ANTHROPIC_AUTH_TOKEN=tp-czicpog6v24c6kuv4db5wbguzrd5rhmgkbeqy8oxp8kaqxkf
set ANTHROPIC_MODEL=mimo-v2.5[1m]
cd /d "E:\claude-code专用文件夹"
claude --enable-auto-mode
