"""Small account persistence interface with SQLite and optional PostgreSQL."""
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path


def _postgres():
    url = os.getenv("DATABASE_URL")
    return url.replace("postgres://", "postgresql://", 1) if url else None


@contextmanager
def _connect():
    url = _postgres()
    if url:
        import psycopg
        from psycopg.rows import dict_row
        conn = psycopg.connect(url, row_factory=dict_row)
        try:
            with conn:
                yield conn, "%s"
        finally:
            conn.close()
        return
    path = Path(os.getenv("APP_DB_PATH", Path(__file__).resolve().parents[1] / "data" / "app.db"))
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        with conn:
            yield conn, "?"
    finally:
        conn.close()


def _ensure(conn, pg):
    if pg == "%s":
        conn.execute("CREATE TABLE IF NOT EXISTS users (id TEXT PRIMARY KEY, email TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL, name TEXT NOT NULL, company TEXT NOT NULL, role TEXT NOT NULL, session_id TEXT NOT NULL, created_at TEXT NOT NULL)")
        conn.execute("CREATE TABLE IF NOT EXISTS tokens (token_hash TEXT PRIMARY KEY, user_id TEXT NOT NULL, expires_at TEXT NOT NULL)")
        conn.execute("CREATE INDEX IF NOT EXISTS tokens_user_idx ON tokens(user_id)")
    else:
        conn.executescript("CREATE TABLE IF NOT EXISTS users (id TEXT PRIMARY KEY, email TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL, name TEXT NOT NULL, company TEXT NOT NULL, role TEXT NOT NULL, session_id TEXT NOT NULL, created_at TEXT NOT NULL); CREATE TABLE IF NOT EXISTS tokens (token_hash TEXT PRIMARY KEY, user_id TEXT NOT NULL, expires_at TEXT NOT NULL); CREATE INDEX IF NOT EXISTS tokens_user_idx ON tokens(user_id);")


def _row(row):
    return dict(row) if row else None


def create_user(user):
    with _connect() as (db, p):
        _ensure(db, p)
        db.execute(f"INSERT INTO users VALUES ({','.join([p]*8)})", tuple(user[k] for k in ("id", "email", "password_hash", "name", "company", "role", "session_id", "created_at")))


def get_user_by_email(email):
    with _connect() as (db, p):
        _ensure(db, p)
        return _row(db.execute(f"SELECT * FROM users WHERE email={p}", (email.lower(),)).fetchone())


def get_user(user_id):
    with _connect() as (db, p):
        _ensure(db, p)
        return _row(db.execute(f"SELECT * FROM users WHERE id={p}", (user_id,)).fetchone())


def get_user_by_session_id(session_id):
    with _connect() as (db, p):
        _ensure(db, p)
        return _row(db.execute(f"SELECT * FROM users WHERE session_id={p}", (session_id,)).fetchone())


def create_token(token_digest, user_id, expires_at):
    with _connect() as (db, p):
        _ensure(db, p)
        db.execute(f"INSERT INTO tokens VALUES ({p},{p},{p})", (token_digest, user_id, expires_at))


def get_user_by_token(token_digest):
    now = datetime.now(timezone.utc).isoformat()
    with _connect() as (db, p):
        _ensure(db, p)
        row = db.execute(f"SELECT u.* FROM tokens t JOIN users u ON u.id=t.user_id WHERE t.token_hash={p} AND t.expires_at>{p}", (token_digest, now)).fetchone()
        return _row(row)


def delete_token(token_digest):
    with _connect() as (db, p):
        _ensure(db, p)
        db.execute(f"DELETE FROM tokens WHERE token_hash={p}", (token_digest,))


def token_expiry():
    return (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
