# BharatAssist AI

A Flask starter for a multilingual AI public-assistance platform.

## Features
- Registration/login
- Password hashing
- Session security
- AI intent routing
- English/Hindi/Kannada script detection
- Education, Government, Career, Agriculture, Health and Emergency modules
- PDF/TXT document extraction
- Dashboard/history
- API endpoint
- Render/Gunicorn ready
- Safe fallback when no LLM API key is configured

## Run on Windows

```bat
py -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
python app.py
```

Open http://127.0.0.1:5000

## Production

Build command:
pip install -r requirements.txt

Start command:
gunicorn app:app

Set a strong SECRET_KEY in your hosting provider's environment variables.

## Important
The included AI is a demo intent router. For a real AI product, connect an LLM and RAG system, ground government/health answers in trusted sources, add OCR/STT/TTS, PostgreSQL, CSRF protection, rate limiting and monitoring.
