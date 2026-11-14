import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path


def _db_path():
    return Path(os.getenv("CHAT_DB_PATH", Path(__file__).resolve().parents[1] / "data" / "chat.db"))


@contextmanager
def _connect():
    path = _db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS sessions(id TEXT PRIMARY KEY, created_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS messages(id TEXT PRIMARY KEY, session_id TEXT NOT NULL, role TEXT NOT NULL, text TEXT NOT NULL, transcript TEXT, sources_json TEXT NOT NULL, cards_json TEXT NOT NULL, created_at TEXT NOT NULL);
    CREATE INDEX IF NOT EXISTS messages_session_created ON messages(session_id, created_at, id);
    CREATE TABLE IF NOT EXISTS profiles(session_id TEXT PRIMARY KEY, json TEXT NOT NULL, updated_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS recommendations(session_id TEXT PRIMARY KEY, status TEXT NOT NULL, json TEXT NOT NULL, fingerprint TEXT NOT NULL, updated_at TEXT NOT NULL, notified INTEGER NOT NULL DEFAULT 0);
    """)
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(messages)")}
    if "blocks_json" not in columns:
        conn.execute("ALTER TABLE messages ADD COLUMN blocks_json TEXT NOT NULL DEFAULT '[]'")
    try:
        with conn:  # commit o rollback
            yield conn
    finally:
        conn.close()


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def create_session(session_id, created_at):
    with _connect() as db:
        db.execute("INSERT INTO sessions VALUES (?, ?)", (session_id, created_at))


def session_exists(session_id):
    with _connect() as db:
        return db.execute("SELECT 1 FROM sessions WHERE id=?", (session_id,)).fetchone() is not None


def add_message(message):
    with _connect() as db:
        db.execute("INSERT INTO messages (id, session_id, role, text, transcript, sources_json, cards_json, created_at, blocks_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", (
            message["id"], message["session_id"], message["role"], message["text"], message.get("transcript"),
            json.dumps(message.get("sources", [])), json.dumps(message.get("cards", [])), message["created_at"], json.dumps(message.get("blocks", []))))


def list_messages(session_id):
    with _connect() as db:
        rows = db.execute("SELECT * FROM messages WHERE session_id=? ORDER BY created_at, rowid", (session_id,)).fetchall()
    return [{"id": r["id"], "role": r["role"], "text": r["text"], "transcript": r["transcript"], "sources": json.loads(r["sources_json"]), "cards": json.loads(r["cards_json"]), "blocks": json.loads(r["blocks_json"]), "created_at": r["created_at"]} for r in rows]


def get_profile(session_id):
    with _connect() as db:
        row = db.execute("SELECT json FROM profiles WHERE session_id=?", (session_id,)).fetchone()
    return json.loads(row[0]) if row else None


def save_profile(session_id, profile):
    with _connect() as db:
        db.execute("INSERT INTO profiles VALUES (?, ?, ?) ON CONFLICT(session_id) DO UPDATE SET json=excluded.json, updated_at=excluded.updated_at", (session_id, json.dumps(profile, ensure_ascii=False), profile["updated_at"]))


def get_recommendations(session_id):
    with _connect() as db:
        row = db.execute("SELECT * FROM recommendations WHERE session_id=?", (session_id,)).fetchone()
    return dict(row) | {"data": json.loads(row["json"])} if row else None


def save_recommendations(session_id, status, data, fingerprint, updated_at=None, notified=0):
    updated_at = updated_at or now_iso()
    with _connect() as db:
        db.execute("INSERT INTO recommendations VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT(session_id) DO UPDATE SET status=excluded.status, json=excluded.json, fingerprint=excluded.fingerprint, updated_at=excluded.updated_at, notified=excluded.notified", (session_id, status, json.dumps(data, ensure_ascii=False), fingerprint, updated_at, notified))


def mark_notified(session_id):
    with _connect() as db:
        db.execute("UPDATE recommendations SET notified=1 WHERE session_id=?", (session_id,))
