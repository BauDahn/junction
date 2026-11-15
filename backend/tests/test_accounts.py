from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

import app as app_module
from accounts import security, store


class _MemoryValkey:
    def __init__(self):
        self.data = {}

    def set(self, key, value, nx=False, ex=None):
        if nx and key in self.data:
            return None
        self.data[key] = str(value)
        return True

    def get(self, key):
        return self.data.get(key)

    def delete(self, key):
        return int(self.data.pop(key, None) is not None)


class _Remote:
    def __init__(self, client):
        self.client = client

    def _run(self, operation):
        try:
            return True, operation(self.client)
        except Exception:
            return False, None


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


def test_shared_valkey_accounts_and_foreign_machine_session(monkeypatch, tmp_path):
    import canonizador.cache

    client = TestClient(app_module.app)
    shared = _MemoryValkey()
    monkeypatch.setenv("ACCOUNTS_STORE", "valkey")
    monkeypatch.setenv("APP_DB_PATH", str(tmp_path / "machine-b.db"))
    monkeypatch.setattr(canonizador.cache, "remote_from_env", lambda: _Remote(shared))
    user_response = _register(client, "investor", "shared@example.com")
    assert user_response.status_code == 201
    data = user_response.json()
    sid = data["user"]["session_id"]
    assert store.get_user(data["user"]["id"])["email"] == "shared@example.com"
    assert store.get_user_by_session_id(sid)["id"] == data["user"]["id"]

    # Another machine has the shared account but an independent, empty chat DB.
    monkeypatch.setenv("APP_DB_PATH", str(tmp_path / "machine-c.db"))
    login = client.post("/api/auth/login", json={"email": "SHARED@example.com", "password": "secret-pass-123"})
    assert login.status_code == 200
    assert login.json()["user"]["id"] == data["user"]["id"]
    from chat import store as chat_store
    assert chat_store.session_exists(sid)
    assert chat_store.get_mode(sid) == "investing"
    assert client.get("/api/me", headers={"Authorization": f"Bearer {login.json()['token']}"}).status_code == 200
    assert client.post("/api/auth/logout", headers={"Authorization": f"Bearer {login.json()['token']}"}).status_code == 204
    assert client.get("/api/me", headers={"Authorization": f"Bearer {login.json()['token']}"}).status_code == 401
    duplicate = _register(client, "investor", "SHARED@example.com")
    assert duplicate.status_code == 409


def test_configured_valkey_failure_returns_503(monkeypatch):
    import canonizador.cache

    class Failing:
        def _run(self, operation):
            return False, None

    monkeypatch.setenv("ACCOUNTS_STORE", "valkey")
    monkeypatch.setattr(canonizador.cache, "remote_from_env", lambda: Failing())
    response = TestClient(app_module.app).post("/api/auth/login", json={"email": "x@example.com", "password": "secret-pass-123"})
    assert response.status_code == 503
    response = TestClient(app_module.app).post("/api/auth/register", json={"email": "x@example.com", "password": "secret-pass-123", "name": "X", "company": "Y", "role": "raiser"})
    assert response.status_code == 503
