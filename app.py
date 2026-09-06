import os
import markdown

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash,
    jsonify,
)

from werkzeug.security import generate_password_hash, check_password_hash

from database import init_db, get_db

from ai.router import route_query
from ai.llm import generate_answer
from ai.language import detect_language
from ai.safety import safety_notice
from ai.rag import build_context

from modules.documents import extract_text

from config import Config


app = Flask(__name__)
app.config.from_object(Config)

init_db()


# ---------------------------------------------------------
# GLOBAL TEMPLATE DATA
# ---------------------------------------------------------

@app.context_processor
def inject_globals():
    return {
        "safety_notice": safety_notice
    }


# ---------------------------------------------------------
# PUBLIC PAGES
# ---------------------------------------------------------

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


# ---------------------------------------------------------
# AUTHENTICATION
# ---------------------------------------------------------

@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not name or not email or len(password) < 6:

            flash(
                "Enter a name, valid email and password of at least 6 characters.",
                "error"
            )

            return render_template("register.html")

        db = get_db()

        try:

            db.execute(
                """
                INSERT INTO users(name, email, password_hash)
                VALUES (?, ?, ?)
                """,
                (
                    name,
                    email,
                    generate_password_hash(password),
                )
            )

            db.commit()

        except Exception:

            flash(
                "Email already registered.",
                "error"
            )

            return render_template("register.html")

        flash(
            "Registration successful. Please log in.",
            "success"
        )

        return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        email = request.form.get(
            "email",
            ""
        ).strip().lower()

        password = request.form.get(
            "password",
            ""
        )

        user = get_db().execute(
            """
            SELECT *
            FROM users
            WHERE email=?
            """,
            (email,)
        ).fetchone()

        if user and check_password_hash(
            user["password_hash"],
            password
        ):

            session.clear()

            session["user_id"] = user["id"]
            session["name"] = user["name"]

            return redirect(
                url_for("dashboard")
            )

        flash(
            "Invalid email or password.",
            "error"
        )

    return render_template("login.html")


@app.route("/logout")
def logout():

    session.clear()

    return redirect(
        url_for("home")
    )


def login_required():
    return "user_id" in session


# ---------------------------------------------------------
# DASHBOARD
# ---------------------------------------------------------

@app.route("/dashboard")
def dashboard():

    if not login_required():
        return redirect(
            url_for("login")
        )

    rows = get_db().execute(
        """
        SELECT *
        FROM conversations
        WHERE user_id=?
        ORDER BY id DESC
        LIMIT 10
        """,
        (session["user_id"],)
    ).fetchall()

    return render_template(
        "dashboard.html",
        rows=rows
    )


# ---------------------------------------------------------
# AI ASSISTANT + RAG
# ---------------------------------------------------------

@app.route("/assistant", methods=["GET", "POST"])
def assistant():

    if not login_required():
        return redirect(
            url_for("login")
        )

    answer = None
    raw_answer = None
    query = ""
    lang = None
    category = None
    sources = []

    if request.method == "POST":

        query = request.form.get(
            "query",
            ""
        ).strip()

        if query:

            # ---------------------------------------------
            # 1. Detect language
            # ---------------------------------------------

            lang = detect_language(query)

            # ---------------------------------------------
            # 2. Detect category
            # ---------------------------------------------

            result = route_query(
                query,
                lang
            )

            category = result.get(
                "category",
                "GENERAL"
            )

            # ---------------------------------------------
            # 3. Search BharatAssist knowledge base
            # ---------------------------------------------

            context, rag_sources = build_context(
                query,
                top_k=3
            )

            # ---------------------------------------------
            # 4. Generate REAL Qwen answer
            # ---------------------------------------------

            raw_answer = generate_answer(
                query,
                lang
            )

            # ---------------------------------------------
            # 5. Convert Markdown to HTML
            # ---------------------------------------------

            answer = markdown.markdown(
                raw_answer,
                extensions=[
                    "extra",
                    "fenced_code",
                    "tables"
                ]
            )

            # ---------------------------------------------
            # 6. Display RAG sources
            # ---------------------------------------------

            if rag_sources:

                sources = rag_sources

            else:

                sources = result.get(
                    "sources",
                    []
                )

            # ---------------------------------------------
            # 7. Save conversation
            # ---------------------------------------------

            db = get_db()

            db.execute(
                """
                INSERT INTO conversations
                (
                    user_id,
                    query,
                    answer,
                    category,
                    language
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    session["user_id"],
                    query,
                    raw_answer,
                    category,
                    lang,
                )
            )

            db.commit()

    return render_template(
        "assistant.html",
        answer=answer,
        query=query,
        language=lang,
        category=category,
        sources=sources,
    )


# ---------------------------------------------------------
# HISTORY
# ---------------------------------------------------------

@app.route("/history")
def history():

    if not login_required():
        return redirect(
            url_for("login")
        )

    rows = get_db().execute(
        """
        SELECT *
        FROM conversations
        WHERE user_id=?
        ORDER BY id DESC
        """,
        (session["user_id"],)
    ).fetchall()

    return render_template(
        "history.html",
        rows=rows
    )


# ---------------------------------------------------------
# HEALTH
# ---------------------------------------------------------

@app.route("/health")
def health():

    return render_template(
        "module.html",
        title="Health Assistant",
        icon="🩺",
        description=(
            "General health information, report explanation "
            "and questions to discuss with a qualified professional."
        ),
        bullets=[
            "Explain health terms in simple language",
            "Summarize non-sensitive text reports",
            "Prepare questions for a doctor",
            "Urgent symptoms should be assessed by local emergency services",
        ],
    )


# ---------------------------------------------------------
# EDUCATION
# ---------------------------------------------------------

@app.route("/education")
def education():

    return render_template(
        "module.html",
        title="Education Assistant",
        icon="🎓",
        description=(
            "Learn topics using summaries, quizzes, "
            "flashcards and simple explanations."
        ),
        bullets=[
            "Explain difficult topics",
            "Generate practice questions",
            "Create study summaries",
            "Build a learning roadmap",
        ],
    )


# ---------------------------------------------------------
# GOVERNMENT
# ---------------------------------------------------------

@app.route("/government")
def government():

    return render_template(
        "module.html",
        title="Government Assistant",
        icon="🏛️",
        description=(
            "Understand government services and schemes "
            "using verified knowledge sources."
        ),
        bullets=[
            "Explain scheme terminology",
            "Create application checklists",
            "Summarize official instructions",
            "Always verify final eligibility on the official portal",
        ],
    )


# ---------------------------------------------------------
# CAREER
# ---------------------------------------------------------

@app.route("/career")
def career():

    return render_template(
        "module.html",
        title="Career Assistant",
        icon="💼",
        description=(
            "Turn your skills and goals into "
            "practical career roadmaps."
        ),
        bullets=[
            "Skill-gap analysis",
            "Learning roadmap",
            "Project ideas",
            "Interview preparation",
        ],
    )


# ---------------------------------------------------------
# AGRICULTURE
# ---------------------------------------------------------

@app.route("/agriculture")
def agriculture():

    return render_template(
        "module.html",
        title="Agriculture Assistant",
        icon="🌾",
        description=(
            "General crop and farming guidance. "
            "Add verified local agriculture data for production use."
        ),
        bullets=[
            "Crop-care guidance",
            "Pest information",
            "Irrigation concepts",
            "Weather-aware planning",
        ],
    )


# ---------------------------------------------------------
# DOCUMENTS
# ---------------------------------------------------------

@app.route("/documents", methods=["GET", "POST"])
def documents():

    if not login_required():
        return redirect(
            url_for("login")
        )

    extracted = None

    if request.method == "POST":

        file = request.files.get(
            "document"
        )

        if not file or not file.filename:

            flash(
                "Choose a PDF, TXT or image file.",
                "error"
            )

        elif len(file.read()) > app.config["MAX_CONTENT_LENGTH"]:

            flash(
                "File is too large.",
                "error"
            )

        else:

            file.stream.seek(0)

            extracted = extract_text(
                file
            )

    return render_template(
        "documents.html",
        extracted=extracted
    )


# ---------------------------------------------------------
# JSON API
# ---------------------------------------------------------

@app.route("/api/ask", methods=["POST"])
def api_ask():

    if not login_required():

        return jsonify({
            "error": "login required"
        }), 401

    data = request.get_json(
        silent=True
    ) or {}

    query = str(
        data.get("query", "")
    ).strip()

    if not query:

        return jsonify({
            "error": "query required"
        }), 400

    # Detect language
    lang = detect_language(
        query
    )

    # Detect category
    result = route_query(
        query,
        lang
    )

    category = result.get(
        "category",
        "GENERAL"
    )

    # Retrieve RAG sources
    context, rag_sources = build_context(
        query,
        top_k=3
    )

    # Generate real Qwen answer
    answer = generate_answer(
        query,
        lang
    )

    return jsonify({
        "answer": answer,
        "category": category,
        "language": lang,
        "sources": rag_sources,
    })


# ---------------------------------------------------------
# APPLICATION START
# ---------------------------------------------------------

if __name__ == "__main__":

    port = int(
        os.environ.get(
            "PORT",
            5000
        )
    )

    app.run(
        host="0.0.0.0",
        port=port,
        debug=True
    )