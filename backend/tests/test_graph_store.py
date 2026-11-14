import fnmatch
import pytest
from graph.model import normalize_name, rels_key, types_compatible, website_key
from graph.store import GraphStore, MemoryKV, ValkeyKV, get_store, reset_store

class FakeRedis:
    def __init__(self): self.data, self.ttl, self.trips = {}, {}, 0
    def get(self,k): self.trips+=1; return self.data.get(k)
    def mget(self,ks):
        if ks: self.trips+=1
        return [self.data.get(k) for k in ks]
    def set(self,k,v,ex=None): self.trips+=1; self.data[k]=v; self.ttl[k]=ex; return True
    def delete(self,*ks):
        self.trips+=1
        for k in ks: self.data.pop(k,None); self.ttl.pop(k,None)
    def sadd(self,k,*xs): self.trips+=1; self.data.setdefault(k,set()).update(xs)
    def srem(self,k,*xs): self.trips+=1; self.data.get(k,set()).difference_update(xs)
    def smembers(self,k): self.trips+=1; return set(self.data.get(k,set()))
    def expire(self,k,t): self.ttl[k]=t
    def ping(self): self.trips+=1; return True
    def pipeline(self): return Pipe(self)
    def scan_iter(self,match):
        self.trips+=1
        return (k for k in self.data if fnmatch.fnmatch(k,match))
class Pipe:
    def __init__(self,c): self.c,self.ops=c,[]
    def __getattr__(self,method):
        def queue(*args,**kwargs): self.ops.append((method,args,kwargs)); return self
        return queue
    def execute(self):
        before=self.c.trips; result=[]
        for method,args,kwargs in self.ops:
            if method=="get": result.append(self.c.data.get(args[0]))
            elif method=="set": result.append(self.c.set(*args,**kwargs))
            elif method=="sadd": result.append(self.c.sadd(*args,**kwargs))
            elif method=="expire": result.append(self.c.expire(*args,**kwargs))
            elif method=="delete": result.append(self.c.delete(*args,**kwargs))
            elif method=="smembers": result.append(set(self.c.data.get(args[0],set())))
        self.c.trips=before+1
        return result

@pytest.fixture(params=["memory","valkey"])
def store(request):
    kv=MemoryKV() if request.param=="memory" else ValkeyKV("redis://fake",client=FakeRedis())
    return GraphStore(kv)
def node(i,typ="Company",name="Amenitiz",website=None):
    return {"id":i,"type":typ,"name":name,"props":{"website":{"value":website}} if website else {}}

def test_pure_model():
    assert normalize_name(" CHALFÉN VENTURES LLP ")=="chalfen ventures"
    assert normalize_name("Foo S.L.")=="foo" and normalize_name("Foo S.R.L.")=="foo"
    assert normalize_name("Ltd")=="ltd" and normalize_name("")==""
    assert types_compatible("Company","Organization") and types_compatible("Product","Product")
    assert not types_compatible("Product","Company") and not types_compatible("Award","Company")
    assert website_key("https://www.Example.com/path")=="example.com" and website_key("") is None

def test_node_ttl_and_all_persisted_ttls(store):
    store.put_node(node("x")); assert store.get_node("x")["id"]=="x"
    assert store.kv.get("graph:v1:node:x")
    store.put_node(node("y",name="Y")); store.put_edge({"src":"x","dst":"y","rel":"INVESTED_IN"})
    store.set_view("u",["x"],["x","y"])
    if isinstance(store.kv,ValkeyKV): assert all(t==604800 for t in store.kv.client.ttl.values())

@pytest.mark.parametrize("reverse",[False,True])
def test_duplicate_companies_and_repoint(store,reverse):
    org=node("o1","Organization","Chalfen Ventures"); company=node("c1","Company","CHALFEN VENTURES LLP")
    store.put_node(company if reverse else org); store.put_node(node("z",name="Other"))
    store.put_edge({"id":"e","src":"o1","dst":"z","rel":"INVESTED_IN"})
    store.put_node(org if reverse else company); merged=store.get_node("c1")
    assert merged["id"]=="c1" and merged["type"]=="Company"
    assert "Chalfen Ventures" in merged["aliases"]
    assert store.get_node("o1")["id"]=="c1" and store.resolve("chalfen ventures llp")=="c1"
    assert store.edges_of("c1")[0]["src"]=="c1"

def test_incompatible_types_and_website_rules(store):
    store.put_node(node("a","Company","Amenitiz")); store.put_node(node("p","Product","Amenitiz"))
    assert store.resolve("Amenitiz")=="a" and store.get_node("p")
    store.put_node(node("w1","Company","Acme","one.com")); store.put_node(node("w2","Organization","Acme","two.com"))
    assert store.get_node("w1") and store.get_node("w2")
    store.put_node(node("w3","Organization","Acme","https://www.one.com/x"))
    assert store.get_node("w3")["id"]=="w1"

def test_get_nodes_batched_and_requested_keys(store):
    for i in range(20): store.put_node(node(str(i),name=f"Entity {i}"))
    store.put_node(node("old","Organization","Entity 0"))
    assert store.canonical_ids(["old","0"])=={"old":"0","0":"0"}
    found=store.get_nodes(["old",*[str(i) for i in range(20)],"absent"])
    assert found["old"]["id"]=="0" and "absent" not in found

def test_edges_idempotency_sources_orientation_and_filters(store):
    for i in "abc": store.put_node(node(i,name=i))
    edge={"id":"e1","src":"a","dst":"b","rel":"INVESTED_IN","sources":[{"name":"n"}]}
    store.put_edge(edge); store.put_edge({**edge,"sources":[{"name":"n"},{"name":"m"}]})
    store.put_edge({"id":"e2","src":"b","dst":"a","rel":"FOUNDED"}); store.put_edge({"id":"e3","src":"a","dst":"c","rel":"WORKS_AT"})
    assert len(store.edges_of("a"))==3 and len(store.edges_of("a",True))==1
    assert len(store.neighbors("a",{"INVESTED_IN"}))==1 and len(store.neighbors("b",{"FOUNDED"}))==1
    assert len(store.neighbors("a",require_sources=True))==1 and len(store.get_edge("e1")["sources"])==2
    assert store.put_edge({"src":"a","dst":"b","rel":"ROLE"})==store.put_edge({"src":"a","dst":"b","rel":"ROLE"})
    saved=store.get_edge("e2"); assert saved["src"]=="b" and saved["dst"]=="a"

def test_distance_multisource_within_and_missing(store):
    for i in "abcd": store.put_node(node(i,name=i))
    for a,b in zip("abc","bcd"): store.put_edge({"id":a+b,"src":b,"dst":a,"rel":"WORKS_AT"})
    assert [store.distance(["a"],x) for x in "abcd"]==[0,1,2,3]
    assert store.distance(["a"],"d",2) is None and store.distance(["a","c"],"d")==1
    assert store.distance(["a"],"c",within={"a","c"}) is None and store.distance(["a"],"missing") is None

def test_views_expansion_and_relations(store):
    for i in "abc": store.put_node(node(i,name=i))
    store.set_view("u",["a"],["a","b"]); store.add_to_view("u",["c"]); store.set_view("v",["b"],["b"])
    assert store.view_seeds("u")==["a"] and store.view_nodes("u")=={"a","b","c"} and store.view_nodes("v")=={"b"}
    assert not store.is_expanded("a","R"); store.mark_expanded("a","R")
    assert store.is_expanded("a","R") and not store.is_expanded("a","R",0)
    assert rels_key(["B","A","A"])==rels_key(["A","B"])
    store.put_expansion(node("a", name="a"), edges=[{"src":"a","dst":"z","rel":"A"}], neighbors=[node("z",name="Z")], rels=["A"])
    assert store.is_expanded("a",["A"]) and store.get_node("z")

def test_rtt_counts_are_batched():
    client=FakeRedis(); graph=GraphStore(ValkeyKV("fake",client=client))
    for i in range(21): graph.put_node(node(str(i),name=f"N{i}"))
    for i in range(1,21): graph.put_edge({"id":f"e{i}","src":"0","dst":str(i),"rel":"INVESTED_IN"})
    client.trips=0; graph.get_nodes([str(i) for i in range(20)]); get_count=client.trips
    client.trips=0; graph.neighbors("0"); neighbors_count=client.trips
    client.trips=0; assert graph.distance(["0"],"20")==1; distance_count=client.trips
    assert get_count==2 and neighbors_count<=4 and distance_count<=6

def test_put_node_roundtrips_do_not_scale_with_candidates():
    client=FakeRedis(); graph=GraphStore(ValkeyKV("fake",client=client))
    graph.put_node(node("only","Company","Acme","only.example"))
    client.trips=0; graph.put_node(node("winner1","Company","Acme")); one_candidate=client.trips
    for i in range(12): graph.put_node(node(f"other{i}","Company","Beta",f"{i}.example"))
    for i in range(12): graph.put_node(node(f"acme{i}","Company","Acme",f"{i}.example"))
    client.trips=0; graph.put_node(node("winner2","Company","Acme")); many_candidates=client.trips
    assert one_candidate<=4 and many_candidates<=4

def test_local_cache_lru_and_invalidation():
    client=FakeRedis(); graph=GraphStore(ValkeyKV("fake",client=client),cache_ttl_s=60,cache_size=2)
    for i in "abc": graph.put_node(node(i,name=i))
    client.trips=0; graph.get_node("a"); first=client.trips; graph.get_node("a")
    assert first==2 and client.trips==first
    graph.get_node("b"); graph.get_node("a"); graph.get_node("c") # b es el LRU que debe salir
    client.trips=0; graph.get_node("b"); assert client.trips==2
    graph.put_node({**node("a"),"props":{"description":{"value":"Changed"}}})
    assert graph.get_node("a")["props"]["description"]["value"]=="Changed"

@pytest.mark.parametrize("backend",["memory","valkey"])
def test_expansion_batch_roundtrips_and_state(backend):
    def make(kv): return GraphStore(kv)
    client=FakeRedis()
    kv=MemoryKV() if backend=="memory" else ValkeyKV("fake",client=client)
    batched=make(kv)
    anchor=node("root",name="Root")
    neighbors=[node(f"n{i}",name=f"N{i}") for i in range(30)]
    edges=[{"id":f"e{i}","src":"root","dst":f"n{i}","rel":"INVESTED_IN"} for i in range(30)]
    if backend=="valkey": client.trips=0
    batched.put_expansion(anchor,edges,neighbors,rels=["INVESTED_IN"])
    assert backend=="memory" or client.trips<=3
    baseline=GraphStore(MemoryKV())
    baseline.put_node(anchor)
    for neighbor in neighbors: baseline.put_node(neighbor)
    for edge in edges: baseline.put_edge(edge)
    baseline.mark_expanded("root",["INVESTED_IN"])
    actual=batched.kv.data if backend=="memory" else batched.kv.client.data
    expected=baseline.kv.data
    assert set(actual)==set(expected)
    def without_dates(raw):
        value=__import__("json").loads(raw)
        value.pop("loaded_at",None)
        value.pop("expanded",None)
        return value
    for key in actual:
        if key.startswith("graph:v1:node:") or key.startswith("graph:v1:edge:"):
            assert without_dates(actual[key])==without_dates(expected[key])
        else:
            assert actual[key]==expected[key]

@pytest.mark.parametrize("backend",["memory","valkey"])
def test_batch_neighbors_distance_and_cache(backend):
    client=FakeRedis()
    kv=MemoryKV() if backend=="memory" else ValkeyKV("fake",client=client)
    graph=GraphStore(kv,cache_size=1000)
    for i in range(25): graph.put_node(node(str(i),name=f"N{i}"))
    for i in range(20):
        for j in range(3):
            graph.put_edge({"id":f"e{i}-{j}","src":str(i),"dst":str(i+1),"rel":"INVESTED_IN"})
    singles={str(i):graph.neighbors(str(i)) for i in range(20)}
    if backend=="valkey": client.trips=0
    batched=graph.neighbors([str(i) for i in range(20)])
    assert batched==singles
    assert backend=="memory" or client.trips<=4
    assert isinstance(graph.neighbors("0"),list)
    graph.distance(["0"],"3")
    if backend=="valkey":
        client.trips=0
        graph.neighbors([str(i) for i in range(20)])
        assert client.trips==0
        client.trips=0
        graph.distance(["0"],"3")
        assert client.trips==0
        graph.put_edge({"id":"new","src":"0","dst":"4","rel":"INVESTED_IN"})
        assert any(edge["id"]=="new" for edge,_ in graph.neighbors("0"))
    tiny=GraphStore(MemoryKV(),cache_size=2)
    for i in "abc": tiny.put_node(node(i,name=i))
    tiny.get_nodes("abc")
    assert len(tiny._local)<=2

@pytest.mark.parametrize("ttl",[60,604800])
def test_all_writes_keep_prefix_and_ttl(ttl):
    client=FakeRedis(); graph=GraphStore(ValkeyKV("fake",client=client),ttl_s=ttl)
    graph.put_node(node("a",name="A")); graph.put_node(node("b",name="B"))
    graph.put_node(node("org","Organization","Merge"))
    graph.put_node(node("co","Company","Merge"))
    graph.put_edge({"id":"e","src":"a","dst":"b","rel":"R"})
    graph.put_expansion(node("a",name="A"),[],[],rels="R")
    graph.set_view("u",["a"],["a","b"]); graph.add_to_view("u",["c"])
    graph.mark_expanded("a","R")
    assert client.data and all(key.startswith("graph:v1:") for key in client.data)
    assert all(value==ttl for value in client.ttl.values())

def test_canonical_batch_merge_and_repoint_roundtrips():
    client=FakeRedis(); graph=GraphStore(ValkeyKV("fake",client=client))
    org=node("org","Organization","Otium Capital")
    company=node("company","Company","OTIUM CAPITAL SAS")
    graph.put_expansion(org,[],[],rels="R")
    graph.put_node(node("linked",name="Linked"))
    graph.put_edge({"id":"prior","src":"org","dst":"linked","rel":"R"})
    client.trips=0
    graph.put_expansion(company,[{"id":"e1","src":"company","dst":"x","rel":"R"},
        {"id":"e2","src":"company","dst":"y","rel":"R"}],
        [node("x",name="X"),node("y",name="Y")],rels="R")
    assert client.trips<=4
    assert graph.get_node("company")["id"]=="company"
    assert graph.get_node("org")["id"]=="company"
    assert all(edge["src"]=="company" for edge in graph.edges_of("company"))

def test_duplicates_within_one_expansion_lot():
    graph=GraphStore(MemoryKV())
    org=node("org","Organization","Otium Capital")
    company=node("company","Company","OTIUM CAPITAL SAS")
    anchor=node("root",name="Root")
    edges=[{"id":"e1","src":"root","dst":"org","rel":"R"},
           {"id":"e2","src":"root","dst":"company","rel":"R"}]
    graph.put_expansion(anchor,edges,[org,company],rels="R")
    assert graph.get_node("org")["id"]=="company"
    assert graph.get_node("company")["id"]=="company"
    assert len(graph.edges_of("root"))==2
    assert all(edge["dst"]=="company" for edge in graph.edges_of("root"))

def test_get_store_fallback_and_singleton(monkeypatch):
    monkeypatch.setenv("VALKEY_URL",""); reset_store(); a=get_store()
    assert a is get_store() and a.backend=="memory"
    monkeypatch.setenv("VALKEY_URL","redis://invalid")
    monkeypatch.setattr("graph.store.ValkeyKV.ping",lambda self:False); reset_store()
    assert get_store().backend=="memory"; reset_store()
