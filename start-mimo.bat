@echo off
cd /d "%~dp0"
echo Starting Xiaomi mimo v2.5-pro (direct, no bridge)...
set ANTHROPIC_BASE_URL=https://token-plan-cn.xiaomimimo.com/anthropic
set ANTHROPIC_AUTH_TOKEN=%MIMO_KEY%
set ANTHROPIC_MODEL=mimo-v2.5-pro
claude --enable-auto-mode

