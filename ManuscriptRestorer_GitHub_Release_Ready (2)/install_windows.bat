@echo off
chcp 65001 >nul
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (
  py -m pip install -r requirements.txt
) else (
  python -m pip install -r requirements.txt
)
if errorlevel 1 echo 依赖安装失败，请参考 README.md
 echo.
 echo 还需要单独安装 Tesseract OCR 程序及 chi_sim 中文语言包。
 echo 若计划使用可选视觉 AI，还需 Ollama 和 qwen3-vl:4b 模型。
pause
