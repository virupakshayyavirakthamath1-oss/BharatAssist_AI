import hashlib
import hmac
import os
import secrets
import smtplib
import ssl
import time
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from urllib.parse import urlparse

from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from werkzeug.middleware.proxy_fix import ProxyFix
from google_auth_oauthlib.flow import Flow
import requests
from dotenv import load_dotenv

load_dotenv()

from database import init_db, get_db
from ai.router import route_query
from ai.language import detect_language
from ai.safety import safety_notice
from modules.documents import extract_text
from config import Config

app = Flask(__name__)
app.config.from_object(Config)
# Render terminates TLS before forwarding requests to Flask.
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)
init_db()

# Lightweight process-local rate limiting. For a multi-instance production deployment,
# move these counters to Redis or another shared store.
_RATE_BUCKETS = {}


def _rate_limited(key, limit, window_seconds):
    now = time.time()
    bucket = _RATE_BUCKETS.setdefault(key, [])
    bucket[:] = [stamp for stamp in bucket if now - stamp < window_seconds]
    if len(bucket) >= limit:
        return True
    bucket.append(now)
    return False


def _client_ip():
    return request.headers.get("X-Forwarded-For", request.remote_addr or "unknown").split(",")[0].strip()


def _csrf_token():
    token = session.get("csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        session["csrf_token"] = token
    return token


@app.context_processor
def inject_globals():
    return {"safety_notice": safety_notice, "csrf_token": _csrf_token()}


@app.before_request
def enforce_csrf():
    if request.method == "POST" and request.endpoint not in {"static"}:
        expected = session.get("csrf_token")
        supplied = request.form.get("csrf_token") or request.headers.get("X-CSRF-Token")
        if not expected or not supplied or not hmac.compare_digest(expected, supplied):
            if request.is_json:
                return jsonify({"error": "invalid csrf token"}), 400
            flash("Your form session expired. Please try again.", "error")
            return redirect(request.referrer or url_for("home"))


@app.after_request
def security_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    if request.is_secure:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


def _utc_now():
    return datetime.now(timezone.utc)


def _parse_dt(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _otp_digest(email, otp):
    raw = f"{email.lower()}:{otp}".encode()
    return hmac.new(app.config["OTP_HASH_SECRET"].encode(), raw, hashlib.sha256).hexdigest()


def _smtp_configured():
    return all([
        app.config["SMTP_HOST"],
        app.config["SMTP_USERNAME"],
        app.config["SMTP_PASSWORD"],
        app.config["MAIL_FROM"],
    ])


def _send_otp(email, otp):
    if not _smtp_configured():
        raise RuntimeError("Email verification is not configured on the server.")

    message = EmailMessage()
    message["Subject"] = "Your BharatAssist AI verification code"
    message["From"] = app.config["MAIL_FROM"]
    message["To"] = email
    message.set_content(
        "Your BharatAssist AI verification code is: " + otp +
        "\n\nThis code expires in " + str(app.config["OTP_TTL_MINUTES"]) +
        " minutes. If you did not request this, you can ignore this email."
    )

    context = ssl.create_default_context()
    with smtplib.SMTP(app.config["SMTP_HOST"], app.config["SMTP_PORT"], timeout=20) as server:
        server.starttls(context=context)
        server.login(app.config["SMTP_USERNAME"], app.config["SMTP_PASSWORD"])
        server.send_message(message)


def _issue_otp(user_id, email, force=False):
    db = get_db()
    user = db.execute("SELECT otp_last_sent_at FROM users WHERE id=?", (user_id,)).fetchone()
    last_sent = _parse_dt(user["otp_last_sent_at"]) if user else None
    if not force and last_sent and (_utc_now() - last_sent).total_seconds() < app.config["OTP_RESEND_SECONDS"]:
        db.close()
        return False, "Please wait before requesting another code."

    otp = f"{secrets.randbelow(1_000_000):06d}"
    expires = _utc_now() + timedelta(minutes=app.config["OTP_TTL_MINUTES"])
    db.execute(
        "UPDATE users SET otp_hash=?, otp_expires_at=?, otp_attempts=0, otp_last_sent_at=? WHERE id=?",
        (_otp_digest(email, otp), expires.isoformat(), _utc_now().isoformat(), user_id),
    )
    db.commit()
    db.close()

    try:
        _send_otp(email, otp)
    except Exception:
        db = get_db()
        db.execute("UPDATE users SET otp_hash=NULL, otp_expires_at=NULL WHERE id=?", (user_id,))
        db.commit()
        db.close()
        raise
    return True, None


def _google_redirect_uri():
    configured = app.config.get("GOOGLE_REDIRECT_URI", "").strip()
    if configured:
        return configured
    return url_for("google_callback", _external=True)


def _google_enabled():
    return bool(app.config.get("GOOGLE_CLIENT_ID") and app.config.get("GOOGLE_CLIENT_SECRET"))


def _google_flow(state=None):
    client_config = {
        "web": {
            "client_id": app.config["GOOGLE_CLIENT_ID"],
            "client_secret": app.config["GOOGLE_CLIENT_SECRET"],
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [_google_redirect_uri()],
        }
    }
    return Flow.from_client_config(
        client_config,
        scopes=["openid", "email", "profile"],
        state=state,
    )


@app.route("/")
def home():
    return render_template("home.html")


@app.route("/features")
def features():
    return render_template("features.html")


@app.route("/how-it-works")
def how_it_works():
    return render_template("how_it_works.html")


@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        if _rate_limited(f"register:{_client_ip()}", 5, 600):
            flash("Too many registration attempts. Please try again later.", "error")
            return render_template("register.html")
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        if not name or "@" not in email or len(password) < 8:
            flash("Enter a valid email and a password of at least 8 characters.", "error")
            return render_template("register.html")
        db = get_db()
        existing = db.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        if existing:
            if not existing["email_verified"]:
                db.close()
                session["verify_user_id"] = existing["id"]
                try:
                    _issue_otp(existing["id"], email)
                except Exception as exc:
                    flash(str(exc), "error")
                    return render_template("register.html")
                flash("That email already has an unverified account. A new code was sent.", "success")
                return redirect(url_for("verify_email"))
            db.close()
            flash("Email already registered. Please log in.", "error")
            return render_template("register.html")

        cur = db.execute(
            "INSERT INTO users(name,email,password_hash,email_verified,auth_provider) VALUES(?,?,?,?,?)",
            (name, email, generate_password_hash(password), 0, "password"),
        )
        user_id = cur.lastrowid
        db.commit()
        db.close()
        try:
            _issue_otp(user_id, email, force=True)
        except Exception as exc:
            flash(str(exc), "error")
            return render_template("register.html")
        session["verify_user_id"] = user_id
        flash("Account created. Enter the verification code sent to your email.", "success")
        return redirect(url_for("verify_email"))
    return render_template("register.html")


@app.route("/verify-email", methods=["GET", "POST"])
def verify_email():
    user_id = session.get("verify_user_id")
    if not user_id:
        return redirect(url_for("register"))
    user = get_db().execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
    if not user:
        session.pop("verify_user_id", None)
        return redirect(url_for("register"))
    if request.method == "POST":
        otp = request.form.get("otp", "").strip()
        if not otp.isdigit() or len(otp) != 6:
            flash("Enter the 6-digit code.", "error")
            return render_template("verify_email.html", email=user["email"])
        if user["otp_attempts"] >= app.config["OTP_MAX_ATTEMPTS"]:
            flash("Too many incorrect attempts. Request a new code.", "error")
            return render_template("verify_email.html", email=user["email"])
        expires = _parse_dt(user["otp_expires_at"])
        if not expires or _utc_now() > expires:
            flash("That code has expired. Request a new code.", "error")
            return render_template("verify_email.html", email=user["email"])
        expected = user["otp_hash"] or ""
        supplied = _otp_digest(user["email"], otp)
        if not hmac.compare_digest(expected, supplied):
            db = get_db()
            db.execute("UPDATE users SET otp_attempts=otp_attempts+1 WHERE id=?", (user_id,))
            db.commit()
            db.close()
            flash("Incorrect verification code.", "error")
            return render_template("verify_email.html", email=user["email"])
        db = get_db()
        db.execute("UPDATE users SET email_verified=1, otp_hash=NULL, otp_expires_at=NULL, otp_attempts=0 WHERE id=?", (user_id,))
        db.commit()
        db.close()
        session.pop("verify_user_id", None)
        session.clear()
        session["user_id"] = user_id
        session["name"] = user["name"]
        flash("Email verified successfully.", "success")
        return redirect(url_for("dashboard"))
    return render_template("verify_email.html", email=user["email"])


@app.route("/resend-otp", methods=["POST"])
def resend_otp():
    user_id = session.get("verify_user_id")
    if not user_id:
        return redirect(url_for("register"))
    user = get_db().execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
    if not user:
        return redirect(url_for("register"))
    try:
        sent, message = _issue_otp(user_id, user["email"])
        if sent:
            flash("A new verification code was sent.", "success")
        else:
            flash(message, "error")
    except Exception as exc:
        flash(str(exc), "error")
    return redirect(url_for("verify_email"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        if _rate_limited(f"login:{_client_ip()}", 10, 300):
            flash("Too many login attempts. Please try again later.", "error")
            return render_template("login.html")
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = get_db().execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        if user and user["password_hash"] and check_password_hash(user["password_hash"], password):
            if not user["email_verified"]:
                session["verify_user_id"] = user["id"]
                try:
                    _issue_otp(user["id"], email)
                except Exception as exc:
                    flash(str(exc), "error")
                    return render_template("login.html")
                flash("Please verify your email before logging in.", "error")
                return redirect(url_for("verify_email"))
            session.clear()
            session["user_id"] = user["id"]
            session["name"] = user["name"]
            return redirect(url_for("dashboard"))
        flash("Invalid email or password.", "error")
    return render_template("login.html")


@app.route("/auth/google")
def google_login():
    if not _google_enabled():
        flash("Google Sign-In is not configured yet.", "error")
        return redirect(url_for("login"))
    state = secrets.token_urlsafe(32)
    session["google_oauth_state"] = state
    flow = _google_flow(state=state)
    authorization_url, _ = flow.authorization_url(
        access_type="online",
        include_granted_scopes="true",
        prompt="select_account",
    )
    return redirect(authorization_url)


@app.route("/auth/google/callback")
def google_callback():
    if not _google_enabled():
        flash("Google Sign-In is not configured yet.", "error")
        return redirect(url_for("login"))
    state = session.pop("google_oauth_state", None)
    if not state or state != request.args.get("state"):
        flash("Google sign-in security check failed. Please try again.", "error")
        return redirect(url_for("login"))
    if request.args.get("error"):
        flash("Google sign-in was cancelled.", "error")
        return redirect(url_for("login"))
    try:
        flow = _google_flow(state=state)
        flow.fetch_token(authorization_response=request.url)
        token = flow.credentials.token
        response = requests.get(
            "https://openidconnect.googleapis.com/v1/userinfo",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10,
        )
        response.raise_for_status()
        profile = response.json()
        google_sub = str(profile.get("sub", "")).strip()
        email = str(profile.get("email", "")).strip().lower()
        name = str(profile.get("name", "Google User")).strip() or "Google User"
        if not google_sub or not email or profile.get("email_verified") is not True:
            raise ValueError("Google did not return a verified email address.")
    except Exception:
        flash("Google sign-in could not be completed. Please try again.", "error")
        return redirect(url_for("login"))

    db = get_db()
    user = db.execute("SELECT * FROM users WHERE google_sub=?", (google_sub,)).fetchone()
    if not user:
        user = db.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
    if user:
        db.execute(
            "UPDATE users SET google_sub=?, email_verified=1, auth_provider=CASE WHEN auth_provider='password' THEN 'google+password' ELSE 'google' END WHERE id=?",
            (google_sub, user["id"]),
        )
        user_id = user["id"]
        user_name = user["name"] or name
    else:
        cur = db.execute(
            "INSERT INTO users(name,email,password_hash,email_verified,google_sub,auth_provider) VALUES(?,?,?,?,?,?)",
            (name, email, "", 1, google_sub, "google"),
        )
        user_id = cur.lastrowid
        user_name = name
    db.commit()
    db.close()
    session.clear()
    session["user_id"] = user_id
    session["name"] = user_name
    flash("Signed in with Google successfully.", "success")
    return redirect(url_for("dashboard"))


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))


def login_required():
    return "user_id" in session


@app.route("/dashboard")
def dashboard():
    if not login_required(): return redirect(url_for("login"))
    rows = get_db().execute(
        "SELECT * FROM conversations WHERE user_id=? ORDER BY id DESC LIMIT 10",
        (session["user_id"],)
    ).fetchall()
    return render_template("dashboard.html", rows=rows)


@app.route("/assistant", methods=["GET", "POST"])
def assistant():
    if not login_required(): return redirect(url_for("login"))
    answer = None
    query = ""
    lang = None
    category = None
    sources = []
    if request.method == "POST":
        query = request.form.get("query", "").strip()
        lang = detect_language(query)
        result = route_query(query, lang)
        answer, category, sources = result["answer"], result["category"], result["sources"]
        db = get_db()
        db.execute("""INSERT INTO conversations(user_id,query,answer,category,language)
                      VALUES(?,?,?,?,?)""", (session["user_id"], query, answer, category, lang))
        db.commit()
    return render_template("assistant.html", answer=answer, query=query, language=lang,
                           category=category, sources=sources)


@app.route("/history")
def history():
    if not login_required(): return redirect(url_for("login"))
    rows = get_db().execute(
        "SELECT * FROM conversations WHERE user_id=? ORDER BY id DESC",
        (session["user_id"],)
    ).fetchall()
    return render_template("history.html", rows=rows)


@app.route("/health")
def health():
    return render_template("module.html", title="Health Assistant", icon="🩺", description="General health information, report explanation and questions to discuss with a qualified professional.", bullets=["Explain health terms in simple language","Summarize non-sensitive text reports","Prepare questions for a doctor","Urgent symptoms should be assessed by local emergency services"])


@app.route("/education")
def education():
    return render_template("module.html", title="Education Assistant", icon="🎓", description="Learn topics using summaries, quizzes, flashcards and simple explanations.", bullets=["Explain difficult topics","Generate practice questions","Create study summaries","Build a learning roadmap"])


@app.route("/government")
def government():
    return render_template("module.html", title="Government Assistant", icon="🏛️", description="Understand government services and schemes using verified knowledge sources.", bullets=["Explain scheme terminology","Create application checklists","Summarize official instructions","Always verify final eligibility on the official portal"])


@app.route("/career")
def career():
    return render_template("module.html", title="Career Assistant", icon="💼", description="Turn your skills and goals into practical career roadmaps.", bullets=["Skill-gap analysis","Learning roadmap","Project ideas","Interview preparation"])


@app.route("/agriculture")
def agriculture():
    return render_template("module.html", title="Agriculture Assistant", icon="🌾", description="General crop and farming guidance. Add verified local agriculture data for production use.", bullets=["Crop-care guidance","Pest information","Irrigation concepts","Weather-aware planning"])


@app.route("/documents", methods=["GET", "POST"])
def documents():
    if not login_required(): return redirect(url_for("login"))
    extracted = None
    if request.method == "POST":
        file = request.files.get("document")
        if not file or not file.filename:
            flash("Choose a PDF, TXT or image file.", "error")
        else:
            payload = file.read()
            if len(payload) > app.config["MAX_CONTENT_LENGTH"]:
                flash("File is too large.", "error")
            else:
                file.stream.seek(0)
                extracted = extract_text(file)
    return render_template("documents.html", extracted=extracted)


@app.route("/api/ask", methods=["POST"])
def api_ask():
    if not login_required(): return jsonify({"error":"login required"}), 401
    data = request.get_json(silent=True) or {}
    query = str(data.get("query", "")).strip()
    if not query: return jsonify({"error":"query required"}), 400
    lang = detect_language(query)
    return jsonify(route_query(query, lang))


@app.route("/healthz")
def healthz():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
