@echo off
chcp 936 >nul
REM ===================================================================
REM DesktopAI-Orchestrator - SSE 服务模式（主推）
REM 用法：start_sse.bat [port] [mode]
REM   例：start_sse.bat            -> 默认端口、配置文件里的 mode
REM       start_sse.bat 8765 mock  -> 指定端口并强制 mock
REM ===================================================================
setlocal
cd /d "%~dp0.."

set PORT=%1
set MODE=%2

set PY=.venv\Scripts\python.exe
if not exist "%PY%" set PY=python

set ARGS=
if not "%PORT%"=="" set ARGS=%ARGS% --port %PORT%
if not "%MODE%"=="" set ARGS=%ARGS% --mode %MODE%

echo [DesktopAI-Orchestrator] 启动 SSE 服务...
echo   配置文件: config\config.yaml
if "%PORT%"=="" (
  echo   端点:     http://127.0.0.1:8765/sse ^(来自 config.yaml^)
) else (
  echo   端点:     http://127.0.0.1:%PORT%/sse
)
echo   按 Ctrl+C 停止
echo.

"%PY%" -m desktop_ai_orchestrator.entry.sse --config config\config.yaml %ARGS%
set EXITCODE=%ERRORLEVEL%

if not "%EXITCODE%"=="0" (
  echo.
  echo [启动失败] 退出码=%EXITCODE%
  echo 排查建议：
  echo   1^) 是否已安装依赖：pip install -r requirements.txt ^&^& pip install -e .
  echo   2^) 配置是否有误：%PY% -m desktop_ai_orchestrator.entry.sse --print-config
  echo   3^) 端口是否被占用：netstat -ano ^| findstr 8765
)

endlocal & exit /b %EXITCODE%
