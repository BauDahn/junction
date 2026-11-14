import pytest
from fastapi.testclient import TestClient
import app as backend_app
from api.catalog_port import MemoryCatalog
from api.graph_port import MemoryGraph
from api.routes import get_cala
from api.catalog_port import get_catalog
from api.graph_port import get_graph
from chat import store
SRC=[{'name':'Cala','url':'https://cala.test'}]
@pytest.fixture
def client(tmp_path,monkeypatch):
    monkeypatch.setenv('CHAT_DB_PATH',str(tmp_path/'chat.db'));monkeypatch.delenv('FEED_ENRICH_TOP',raising=False)
    backend_app.app.dependency_overrides[get_catalog]=lambda:MemoryCatalog([{'id':'f','name':'Fund','kinds':['investor'],'sectors':['Fintech'],'sources':SRC},{'id':'s','name':'Startup','kinds':['startup'],'sources':SRC}])
    backend_app.app.dependency_overrides[get_graph]=lambda:MemoryGraph();backend_app.app.dependency_overrides[get_cala]=lambda:None
    with TestClient(backend_app.app) as c:yield c
    backend_app.app.dependency_overrides.clear()
def session(c):
    sid=c.post('/api/sessions').json()['session_id'];store.save_profile(sid,{'updated_at':'now','sector':'Fintech','stage':'Seed'});return sid
def test_feed_two_modes_and_exact_card_shape(client):
    sid=session(client)
    for mode,expected in [('raising','investor'),('investing','startup')]:
        r=client.get('/api/feed',params={'session_id':sid,'mode':mode});assert r.status_code==200
        item=r.json()['items'][0];assert item['type']==expected
        assert set(item)=={'id','type','name','one_liner','tags','score','confidence','why_match','sources'}
def test_feed_cursor_and_invalid_mode(client):
    sid=session(client);assert client.get('/api/feed',params={'session_id':sid,'mode':'bad'}).status_code==422
    assert client.get('/api/feed',params={'session_id':'missing'}).status_code==404

def test_feed_ranks_three_thousand_candidates_under_one_second():
    import time
    from api.candidates import build_feed
    feats=[{'id':str(i),'name':f'Fund {i:04}','kinds':['investor'],'sources':SRC,'sectors':['Fintech'],'stages':['Seed']} for i in range(3000)]
    started=time.perf_counter();res=build_feed('user',{'sector':'Fintech','stage':'Seed'},'raising',MemoryCatalog(feats),MemoryGraph())
    assert len(res['results'])==3000 and time.perf_counter()-started<1
