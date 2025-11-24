@echo off
REM 快速启动脚本 - Windows批处理文件
echo ======================================
echo 通达信AI选股系统 - 快速启动
echo ======================================
echo.

REM 检查虚拟环境是否存在
if not exist "venv\Scripts\activate.bat" (
    echo [错误] 未找到虚拟环境!
    echo 请先运行: python -m venv venv
    echo 然后运行: venv\Scripts\pip.exe install -r requirements.txt
    pause
    exit /b 1
)

REM 激活虚拟环境并启动服务
echo [1/2] 激活虚拟环境...
call venv\Scripts\activate.bat

echo [2/2] 启动服务...
echo.
echo 访问地址: http://localhost:8000
echo API文档: http://localhost:8000/docs
echo.
echo 按 Ctrl+C 停止服务
echo ======================================
echo.

python main.py
