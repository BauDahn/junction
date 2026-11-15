"""Account persistence with an optional shared Valkey store."""
import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path


class StoreUnavailable(RuntimeError):
    """The configured shared account store cannot be reached."""


def _postgres():
    url = os.getenv("DATABASE_URL")
    return url.replace("postgres://", "postgresql://", 1) if url else None


def _backend():
    choice = (os.getenv("ACCOUNTS_STORE") or "").strip().lower()
    if choice not in ("", "valkey", "sqlite", "postgres"):
        raise ValueError("ACCOUNTS_STORE must be valkey, sqlite, or postgres")
    if choice == "valkey" or (not choice and (os.getenv("VALKEY_URL") or "").strip()):
        return "valkey"
    if choice == "postgres" or (not choice and _postgres()):
        return "postgres"
    return "sqlite"


def _remote():
    from canonizador.cache import remote_from_env
    remote = remote_from_env()
    if remote is None:
        raise StoreUnavailable("Account store is Valkey but VALKEY_URL is not configured")
    return remote


def _run(operation):
    ok, result = _remote()._run(operation)
    if not ok:
        raise StoreUnavailable("Shared account store is unavailable")
    return result


def _key(kind, value):
    return f"acct:v1:{kind}:{value}"


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


def _remote_user(client, user_id):
    raw = client.get(_key("user", user_id))
    return json.loads(raw) if raw else None


def create_user(user):
    if _backend() == "valkey":
        raw = json.dumps(user, ensure_ascii=False, separators=(",", ":"))
        def write(client):
            email_key = _key("email", user["email"].lower())
            if not client.set(email_key, user["id"], nx=True):
                return False
            client.set(_key("user", user["id"]), raw)
            client.set(_key("session", user["session_id"]), user["id"])
            return True
        if not _run(write):
            raise sqlite3.IntegrityError("UNIQUE constraint failed: users.email")
        return
    with _connect() as (db, p):
        _ensure(db, p)
        db.execute(f"INSERT INTO users VALUES ({','.join([p]*8)})", tuple(user[k] for k in ("id", "email", "password_hash", "name", "company", "role", "session_id", "created_at")))


def get_user_by_email(email):
    if _backend() == "valkey":
        return _get_email_valkey(email)
    with _connect() as (db, p):
        _ensure(db, p)
        return _row(db.execute(f"SELECT * FROM users WHERE email={p}", (email.lower(),)).fetchone())


def _get_email_valkey(email):
    def read(client):
        user_id = client.get(_key("email", email.lower()))
        return _remote_user(client, user_id) if user_id else None
    return _run(read)


def get_user(user_id):
    if _backend() == "valkey":
        return _run(lambda c: _remote_user(c, user_id))
    with _connect() as (db, p):
        _ensure(db, p)
        return _row(db.execute(f"SELECT * FROM users WHERE id={p}", (user_id,)).fetchone())


def get_user_by_session_id(session_id):
    if _backend() == "valkey":
        def read(client):
            user_id = client.get(_key("session", session_id))
            return _remote_user(client, user_id) if user_id else None
        return _run(read)
    with _connect() as (db, p):
        _ensure(db, p)
        return _row(db.execute(f"SELECT * FROM users WHERE session_id={p}", (session_id,)).fetchone())


def create_token(token_digest, user_id, expires_at):
    if _backend() == "valkey":
        expiry = datetime.fromisoformat(expires_at)
        ttl = max(1, int((expiry - datetime.now(expiry.tzinfo or timezone.utc)).total_seconds()))
        _run(lambda c: c.set(_key("token", token_digest), user_id, ex=ttl))
        return
    with _connect() as (db, p):
        _ensure(db, p)
        db.execute(f"INSERT INTO tokens VALUES ({p},{p},{p})", (token_digest, user_id, expires_at))


def get_user_by_token(token_digest):
    if _backend() == "valkey":
        def read(client):
            user_id = client.get(_key("token", token_digest))
            return _remote_user(client, user_id) if user_id else None
        return _run(read)
    now = datetime.now(timezone.utc).isoformat()
    with _connect() as (db, p):
        _ensure(db, p)
        row = db.execute(f"SELECT u.* FROM tokens t JOIN users u ON u.id=t.user_id WHERE t.token_hash={p} AND t.expires_at>{p}", (token_digest, now)).fetchone()
        return _row(row)


def delete_token(token_digest):
    if _backend() == "valkey":
        _run(lambda c: c.delete(_key("token", token_digest)))
        return
    with _connect() as (db, p):
        _ensure(db, p)
        db.execute(f"DELETE FROM tokens WHERE token_hash={p}", (token_digest,))


def token_expiry():
    return (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
