import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "bharatassist.db"


def get_db():
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    return db


def _add_column(db, table, column, definition):
    try:
        db.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
    except sqlite3.OperationalError as exc:
        if "duplicate column name" not in str(exc).lower():
            raise


def init_db():
    db = get_db()
    db.executescript("""
    CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL DEFAULT '',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS conversations(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        query TEXT NOT NULL,
        answer TEXT NOT NULL,
        category TEXT,
        language TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(user_id) REFERENCES users(id)
    );
    """)

    # Migrate older BharatAssist databases without destroying existing users.
    _add_column(db, "users", "email_verified", "INTEGER NOT NULL DEFAULT 0")
    _add_column(db, "users", "otp_hash", "TEXT")
    _add_column(db, "users", "otp_expires_at", "TIMESTAMP")
    _add_column(db, "users", "otp_attempts", "INTEGER NOT NULL DEFAULT 0")
    _add_column(db, "users", "otp_last_sent_at", "TIMESTAMP")
    _add_column(db, "users", "google_sub", "TEXT")
    _add_column(db, "users", "auth_provider", "TEXT NOT NULL DEFAULT 'password'")
    db.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_google_sub ON users(google_sub) WHERE google_sub IS NOT NULL")
    db.commit()
    db.close()
