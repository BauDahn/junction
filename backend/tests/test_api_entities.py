from fastapi.testclient import TestClient
import app as backend_app
from api.catalog_port import MemoryCatalog,get_catalog
from api.graph_port import MemoryGraph,get_graph
from api.routes import get_cala
from chat import store

def test_entity_not_found_and_mode_save(tmp_path,monkeypatch):
    monkeypatch.setenv('CHAT_DB_PATH',str(tmp_path/'chat.db'))
    backend_app.app.dependency_overrides[get_catalog]=lambda:MemoryCatalog()
    backend_app.app.dependency_overrides[get_graph]=lambda:MemoryGraph();backend_app.app.dependency_overrides[get_cala]=lambda:None
    with TestClient(backend_app.app) as c:
        sid=c.post('/api/sessions').json()['session_id']
        assert c.get('/api/entities/nope').status_code==404
        assert c.post(f'/api/sessions/{sid}/mode',json={'mode':'investing'}).json()=={'mode':'investing'}
        assert store.get_mode(sid)=='investing'
        assert c.get('/api/feed',params={'session_id':sid}).json()['mode']=='investing'
    backend_app.app.dependency_overrides.clear()
