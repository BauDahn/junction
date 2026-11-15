import time

from fastapi.testclient import TestClient

import app as backend_app
from api.catalog_port import MemoryCatalog, get_catalog
from api.graph_port import MemoryGraph, get_graph
from api import routes
from api.routes import get_cala


def _reset_stats():
    with routes._stats_lock:
        routes._stats_local = None
        routes._stats_local_at = 0
        routes._stats_refreshing = False


def test_stats_5000_catalog_is_fast_and_uses_cache(monkeypatch):
    _reset_stats()
    records = [{"id": str(i), "name": f"Company {i}", "kinds": ["investor" if i % 2 else "startup"]}
               for i in range(5000)]
    catalog = MemoryCatalog(records)
    backend_app.app.dependency_overrides[get_catalog] = lambda: catalog
    backend_app.app.dependency_overrides[get_graph] = lambda: MemoryGraph()
    backend_app.app.dependency_overrides[get_cala] = lambda: None
    with TestClient(backend_app.app) as client:
        started = time.monotonic()
        response = client.get("/api/stats")
        assert response.status_code == 200
        assert time.monotonic() - started < 1
        first = response.json()
        assert first["catalog"]["status"] == "pending"
        deadline = time.monotonic() + 2
        while routes._stats_local is None and time.monotonic() < deadline:
            time.sleep(0.01)
        assert routes._stats_local["catalog"]["total"] == 5000
        started = time.monotonic()
        second = client.get("/api/stats")
        assert time.monotonic() - started < 1
        assert second.json()["catalog"]["total"] == 5000
    backend_app.app.dependency_overrides.clear()
    _reset_stats()


def test_stats_detail_requires_admin_token(monkeypatch):
    _reset_stats()
    monkeypatch.setenv("ADMIN_TOKEN", "stats-test-token")
    class Cala:
        stats = {"calls": 2}
    routes._refresh_stats(MemoryCatalog(), Cala(), None)
    backend_app.app.dependency_overrides[get_catalog] = MemoryCatalog
    backend_app.app.dependency_overrides[get_graph] = lambda: MemoryGraph()
    backend_app.app.dependency_overrides[get_cala] = Cala
    with TestClient(backend_app.app) as client:
        public = client.get("/api/stats").json()
        assert "by_who" not in public["cala_usage"]
        assert "by_class" not in public["cala_usage"]
        admin = client.get("/api/stats", headers={"X-Admin-Token": "stats-test-token"}).json()
        assert "by_who" in admin["cala_usage"]
        assert "by_class" in admin["cala_usage"]
    backend_app.app.dependency_overrides.clear()
    _reset_stats()
