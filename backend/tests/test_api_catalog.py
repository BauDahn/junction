import json
from api.catalog_port import MemoryCatalog, ValkeyCatalog, normalize_features

def test_normalize_features_aliases_and_missing_fields():
    f=normalize_features({'id':4,'name':'A','is_investor':True,'sector':'AI','stage':'Seed','amount_min':'10','region':'Nordics'})
    assert f['kinds']==['investor'] and f['sectors']==['AI'] and f['stages']==['Seed']
    assert f['amount']=={'min':10.0,'max':None} and f['hq']=='Nordics' and f['sources']==[]
    assert normalize_features({'id':'x'}) is None

def test_normalize_features_activity_counts_are_integers():
    feature = normalize_features({"id": "x", "name": "X", "activity": {"rounds_24m": 4.0, "led_24m": "2"}})
    assert feature["activity"] == {"rounds_24m": 4, "led_24m": 2}
    assert type(feature["activity"]["rounds_24m"]) is int
    assert type(feature["activity"]["led_24m"]) is int

def test_valkey_reads_features_in_batches_not_gets():
    raw={'name':'X','kinds':['investor']}
    class Pipe:
        def __init__(self,c):self.c=c;self.chunks=[]
        def mget(self,keys):self.chunks.append(keys)
        def execute(self):return [[json.dumps(raw | {'id':key.rsplit(':',1)[-1]}) for key in keys] for keys in self.chunks]
    class Client:
        def __init__(self):self.gets=[];self.pipes=0;self.pipeline_calls=0
        def scan_iter(self,**kw):return [f"cat:v1:feat:{i}" for i in range(501)]
        def pipeline(self):self.pipeline_calls+=1;return Pipe(self)
        def get(self,key):self.gets.append(key);return '{}'
    class Remote:
        def __init__(self):self.client=Client()
        def _run(self,fn):return True,fn(self.client)
    remote=Remote();cat=ValkeyCatalog(remote,refresh_s=30)
    assert len(cat.list_features('investor'))==501
    assert remote.client.pipeline_calls==1 and remote.client.gets==['cat:v1:status']


def test_valkey_load_flattens_redis_pipeline_results_for_multiple_chunks():
    class Pipe:
        def __init__(self): self.commands=[]
        def mget(self, keys): self.commands.append(list(keys))
        def execute(self):
            return [[json.dumps({'id':key.rsplit(':',1)[-1], 'name':'Fund', 'kinds':['investor']})
                     for key in chunk] for chunk in self.commands]
    class Client:
        def __init__(self): self.pipeline_count=0; self.feature_gets=0
        def scan_iter(self, **kwargs): return [f'cat:v1:feat:{i}' for i in range(600)]
        def pipeline(self): self.pipeline_count+=1; return Pipe()
        def get(self, key):
            if key.startswith('cat:v1:feat:'): self.feature_gets+=1
            return '{}'
    class Remote:
        def __init__(self): self.client=Client()
        def _run(self, fn): return True, fn(self.client)
    remote=Remote(); catalog=ValkeyCatalog(remote, refresh_s=30)
    features=catalog.list_features('investor')
    assert len(features)==600
    assert features[0]['id']=='0' and features[-1]['id']=='599'
    assert remote.client.pipeline_count==1
    assert remote.client.feature_gets==0


def test_valkey_catalog_refresh_uses_environment_interval(monkeypatch):
    monkeypatch.setenv("CATALOG_REFRESH_S", "45")
    class Pipe:
        def mget(self, keys):
            self.keys = keys

        def execute(self):
            return [[json.dumps({"id": "fund", "name": "Fund", "kinds": ["investor"]})]]

    class Client:
        def __init__(self):
            self.loads = 0

        def scan_iter(self, **kwargs):
            self.loads += 1
            return ["cat:v1:feat:fund"]

        def pipeline(self):
            return Pipe()

        def get(self, key):
            return '{"done":1,"total":1}'

    class Remote:
        def __init__(self):
            self.client = Client()

        def _run(self, operation):
            return True, operation(self.client)

    remote = Remote()
    catalog = ValkeyCatalog(remote)
    assert catalog.list_features("investor")[0]["id"] == "fund"
    catalog.list_features("investor")
    assert catalog.refresh_s == 45
    assert remote.client.loads == 1


def test_valkey_catalog_failure_is_tolerated():
    class Remote:
        def _run(self, operation):
            return False, None

    catalog = ValkeyCatalog(Remote())
    assert catalog.list_features("investor") == []
    assert catalog.status() == {}


def test_memory_graph_neighbors_get_nodes_and_distance():
    from api.graph_port import MemoryGraph
    graph = MemoryGraph()
    graph.add_node({"id": "a", "name": "A", "aliases": ["Alpha"], "props": {}})
    graph.add_node({"id": "b", "name": "B", "props": {}})
    graph.add_node({"id": "c", "name": "C", "props": {}})
    graph.add_edge({"id": "ab", "src": "a", "dst": "b", "rel": "INVESTED_IN", "sources": []})
    graph.add_edge({"id": "bc", "src": "b", "dst": "c", "rel": "INVESTED_IN", "sources": []})
    assert graph.neighbors("a")[0][1]["id"] == "b"
    assert list(graph.neighbors(["a", "missing"])) == ["a", "missing"]
    assert graph.get_nodes(["a", "missing"])["a"]["name"] == "A"
    assert graph.distance(["a"], "c") == 2
    assert graph.resolve("ALPHA") == "a"
