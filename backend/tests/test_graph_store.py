import pytest
from graph.model import normalize_name, types_compatible, website_key
from graph.store import GraphStore, MemoryKV, ValkeyKV, get_store, reset_store

class FakeRedis:
    def __init__(self): self.data, self.ttl = {}, {}
    def get(self,k): return self.data.get(k)
    def mget(self,ks): return [self.get(k) for k in ks]
    def set(self,k,v,ex=None): self.data[k]=v; self.ttl[k]=ex; return True
    def delete(self,k): self.data.pop(k,None)
    def sadd(self,k,*xs): self.data.setdefault(k,set()).update(xs)
    def srem(self,k,*xs): self.data.get(k,set()).difference_update(xs)
    def smembers(self,k): return set(self.data.get(k,set()))
    def expire(self,k,t): self.ttl[k]=t
    def ping(self): return True
    def pipeline(self): return Pipe(self)
    def scan_iter(self,match):
        import fnmatch
        return (k for k in self.data if fnmatch.fnmatch(k,match))
class Pipe:
    def __init__(self,c): self.c,self.ops=c,[]
    def smembers(self,k): self.ops.append(k)
    def execute(self): return [self.c.smembers(k) for k in self.ops]

@pytest.fixture(params=["memory","valkey"])
def store(request):
    kv=MemoryKV() if request.param=="memory" else ValkeyKV("redis://fake",client=FakeRedis())
    return GraphStore(kv)
def node(i,typ="Company",name="Amenitiz",website=None):
    return {"id":i,"type":typ,"name":name,"props":{"website":{"value":website}} if website else {}}

def test_pure_normalization():
    assert normalize_name(" CHALFÉN VENTURES LLP ")=="chalfen ventures"
    assert normalize_name("Foo S.L.")=="foo" and normalize_name("S.R.L.")=="s r l"
    assert normalize_name("")==""
    assert types_compatible("Company","Organization") and not types_compatible("Product","Company")
    assert website_key("https://www.Example.com/path")=="example.com"

def test_roundtrip_ttl(store):
    store.put_node(node("x")); assert store.get_node("x")["id"]=="x"
    assert store.kv.get("graph:v1:node:x")
    if isinstance(store.kv,ValkeyKV): assert store.kv.client.ttl["graph:v1:node:x"]==604800

@pytest.mark.parametrize("reverse",[False,True])
def test_company_merge_and_edge_repoint(store,reverse):
    org=node("o1","Organization","Chalfen Ventures"); co=node("c1","Company","CHALFEN VENTURES LLP")
    store.put_node(co if reverse else org)
    store.put_node(node("z",name="Other")); store.put_edge({"id":"e","src":"o1","dst":"z","rel":"INVESTED_IN"})
    store.put_node(org if reverse else co)
    assert store.get_node("o1")["id"]=="c1" and store.resolve("chalfen ventures llp")=="c1"
    assert store.get_node("c1")["type"]=="Company" and "Chalfen Ventures" in store.get_node("c1")["aliases"]
    assert store.edges_of("c1")[0]["src"]=="c1"

def test_type_and_website_disambiguation(store):
    store.put_node(node("a","Company","Amenitiz")); store.put_node(node("p","Product","Amenitiz"))
    assert store.resolve("Amenitiz")=="a" and store.get_node("p")
    store.put_node(node("w1","Company","Acme","one.com")); store.put_node(node("w2","Organization","Acme","two.com"))
    assert store.get_node("w1") and store.get_node("w2")
    store.put_node(node("w3","Organization","Acme","https://www.one.com/x"))
    assert store.get_node("w3")["id"]=="w1"

def test_edges_neighbors(store):
    for i in "ab": store.put_node(node(i,name=i))
    store.put_edge({"id":"e1","src":"a","dst":"b","rel":"INVESTED_IN","sources":[{"name":"n"}]})
    store.put_edge({"id":"e1","src":"a","dst":"b","rel":"INVESTED_IN","sources":[{"name":"n"},{"name":"m"}]})
    store.put_edge({"id":"e2","src":"b","dst":"a","rel":"FOUNDED"})
    assert len(store.edges_of("a"))==2 and len(store.edges_of("a",True))==1
    assert len(store.neighbors("a",{"INVESTED_IN"}))==1 and len(store.neighbors("a",require_sources=True))==1
    assert len(store.get_edge("e1")["sources"])==2
    assert store.put_edge({"src":"a","dst":"b","rel":"WORKS_AT"})==store.put_edge({"src":"a","dst":"b","rel":"WORKS_AT"})

def test_distance_views_expanded(store):
    for i in "abcd": store.put_node(node(i,name=i))
    for a,b in zip("abc","bcd"): store.put_edge({"id":a+b,"src":a,"dst":b,"rel":"WORKS_AT"})
    assert [store.distance(["a"],x) for x in "abcd"]==[0,1,2,3]
    assert store.distance(["a"],"d",2) is None and store.distance(["a","c"],"d")==1
    assert store.distance(["a"],"c",within={"a","c"}) is None and store.distance(["a"],"missing") is None
    store.set_view("u",["a"],["a","b"]); store.add_to_view("u",["c"]); store.set_view("v",["d"],["d"])
    assert store.view_seeds("u")==["a"] and store.view_nodes("u")=={"a","b","c"} and store.view_nodes("v")=={"d"}
    assert store.get_node("a") and not store.is_expanded("a","WORKS_AT")
    store.mark_expanded("a","WORKS_AT")
    assert store.is_expanded("a","WORKS_AT") and not store.is_expanded("a","WORKS_AT",0)

def test_get_store_fallback(monkeypatch):
    monkeypatch.setenv("VALKEY_URL",""); reset_store(); a=get_store()
    assert a is get_store() and a.backend=="memory"
    monkeypatch.setenv("VALKEY_URL","redis://invalid")
    monkeypatch.setattr("graph.store.ValkeyKV.ping",lambda self:False); reset_store()
    assert get_store().backend=="memory"; reset_store()
