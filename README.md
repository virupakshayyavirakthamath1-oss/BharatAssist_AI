# BharatAssist AI — Upgraded

A Flask-based multilingual public-assistance assistant for English, Hindi and Kannada.

## What was upgraded

- Gemini API integration using HTTPS REST (no OpenAI dependency)
- Free-tier-friendly Gemini model: `gemini-3.5-flash-lite`
- Optional Google Search grounding for current/fresh questions
- Lightweight local RAG over `data/**/*.txt`
- Category routing for Health, Education, Government, Agriculture, Career, Documents and Emergency
- Source/verification display
- Safer prompts that discourage invented facts
- Existing login, registration, dashboard, history, document extraction and API routes preserved
- Render/Gunicorn compatible

## Important accuracy note

No AI model can guarantee 100% correct answers to every question. BharatAssist is designed to reduce hallucinations by using local context and, for freshness-sensitive questions, optional Google Search grounding. Important health, legal, government and emergency decisions must still be verified with qualified professionals or official sources.

## Free usage

Gemini has a free tier, but it has rate limits. It is **not unlimited**. Google may change models and limits over time. See Google's current Gemini pricing and rate-limit documentation before production use.

## Windows setup

```bat
py -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
set GEMINI_API_KEY=YOUR_KEY_HERE
python app.py
```

Then open `http://127.0.0.1:5000`.

For PowerShell, use:

```powershell
$env:GEMINI_API_KEY="YOUR_KEY_HERE"
python app.py
```

## Render

Build command:

```text
pip install -r requirements.txt
```

Start command:

```text
gunicorn app:app
```

Set these environment variables in Render:

```text
SECRET_KEY=<long-random-secret>
GEMINI_API_KEY=<your-gemini-key>
GEMINI_MODEL=gemini-3.5-flash-lite
GEMINI_USE_SEARCH=auto
COOKIE_SECURE=1
```

Never put the real API key inside Python files or commit it to GitHub.

## Authentication and security

BharatAssist AI supports two login methods:

1. **Continue with Google** using Google OpenID Connect (`openid`, `email`, `profile`).
2. **Email + password + email OTP verification**. Registration requires ownership of the email address.

Additional protections include CSRF tokens, password hashing, secure session-cookie settings, login/registration rate limiting, OTP expiry/attempt limits, security headers, and Google OAuth `state` validation.

### Google OAuth setup

Create a Google OAuth 2.0 **Web application** client. Add the production redirect URI:

```text
https://bharatassist-ai.onrender.com/auth/google/callback
```

For local development also add:

```text
http://127.0.0.1:5000/auth/google/callback
http://localhost:5000/auth/google/callback
```

Authorized JavaScript origin:

```text
https://bharatassist-ai.onrender.com
```

Set these environment variables:

```text
GOOGLE_CLIENT_ID=<client id>
GOOGLE_CLIENT_SECRET=<client secret>
GOOGLE_REDIRECT_URI=https://bharatassist-ai.onrender.com/auth/google/callback
```

Never commit the client secret to GitHub.

### Gmail OTP setup

Use a Google App Password rather than your normal Gmail password:

```text
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=<sender Gmail address>
SMTP_PASSWORD=<Google App Password>
MAIL_FROM=<sender Gmail address>
```

Then configure `OTP_HASH_SECRET` with a long random secret. On Render, set `COOKIE_SECURE=1` because the public site uses HTTPS.
