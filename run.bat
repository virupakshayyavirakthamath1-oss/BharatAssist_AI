@echo off
setlocal
if not exist .venv (
  py -m venv .venv
)
call .venv\Scripts\activate.bat
python -m pip install -r requirements.txt
if "%GEMINI_API_KEY%"=="" (
  echo.
  echo GEMINI_API_KEY is not set. The website will start in offline/demo mode.
  echo To enable full AI answers, set GEMINI_API_KEY before running.
  echo.
)
python app.py
endlocal
