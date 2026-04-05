@echo off
setlocal


if "%DEEPSEEK_API_KEY%"=="" (
    echo [error] DEEPSEEK_API_KEY not set
    echo Please set in env
    pause
    exit /b 1
)

echo [info] Starting Claude Code with router...
ccr code --dangerously-skip-permissions