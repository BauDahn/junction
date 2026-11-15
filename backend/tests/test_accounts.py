from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

import app as app_module
from accounts import security, store


def _client(monkeypatch, tmp_path):
    monkeypatch.setenv("APP_DB_PATH", str(tmp_path / "app.db"))
    monkeypatch.delenv("DATABASE_URL", raising=False)
    return TestClient(app_module.app)


def _register(client, role="raiser", email="founder@example.com"):
    return client.post("/api/auth/register", json={"email": email, "password": "secret-pass-123", "name": "A Founder", "company": "Acme", "role": role})


def test_register_login_duplicate_and_password_safety(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path)
    response = _register(client)
    assert response.status_code == 201
    data = response.json()
    assert data["token"] and data["user"]["session_id"]
    assert "secret-pass-123" not in response.text
    saved = store.get_user_by_email("founder@example.com")
    assert saved["password_hash"] != "secret-pass-123"
    assert client.post("/api/auth/register", json={"email": "FOUNDER@example.com", "password": "secret-pass-123", "name": "A", "company": "B", "role": "raiser"}).status_code == 409
    assert client.post("/api/auth/login", json={"email": "founder@example.com", "password": "secret-pass-123"}).status_code == 200
    bad = client.post("/api/auth/login", json={"email": "founder@example.com", "password": "wrong-pass"})
    assert bad.status_code == 401 and bad.json()["error"]["code"] == "invalid_credentials"
    assert "secret-pass-123" not in bad.text


def test_me_logout_and_expired_token(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path)
    data = _register(client).json()
    assert client.get("/api/me").status_code == 401
    headers = {"Authorization": f"Bearer {data['token']}"}
    assert client.get("/api/me", headers=headers).json()["id"] == data["user"]["id"]
    assert client.post("/api/auth/logout", headers=headers).status_code == 204
    assert client.get("/api/me", headers=headers).status_code == 401
    login = client.post("/api/auth/login", json={"email": "founder@example.com", "password": "secret-pass-123"}).json()
    digest = security.token_hash(login["token"])
    store.delete_token(digest)
    store.create_token(digest, login["user"]["id"], (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat())
    expired = client.get("/api/me", headers={"Authorization": f"Bearer {login['token']}"})
    assert expired.status_code == 401


def test_role_locked_for_account_and_anonymous_mode_works(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path)
    user = _register(client, "raiser").json()["user"]
    assert client.post(f"/api/sessions/{user['session_id']}/mode", json={"mode": "investing"}).status_code == 409
    response = client.post(f"/api/sessions/{user['session_id']}/mode", json={"mode": "raising"})
    assert response.status_code == 200
    assert response.json() == {"mode": "raising"}
