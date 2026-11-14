import asyncio
from collections import Counter
from types import SimpleNamespace
import json
import pytest

from graph.loader import EXPAND_KEY, expand_node, load_neighborhood, resolve_seeds
from graph.store import GraphStore, MemoryKV, ValkeyKV
from graph import preload
from graph_fakes import FakeRedis

SOURCES = [{"name":"Cala","document":"d","date":"2026"}]
def item(ident,name,typ,edge,**props):
    return {"id":ident,"name":name,"entity_type":typ,"properties":{"id":edge,"sources":SOURCES,**props}}

def raw(ident,name,typ,rels=None,props=None):
    return {"id":ident,"name":name,"entity_type":typ,"properties":props or {},"relationships":rels or {"incoming":{},"outgoing":{}}}

class FakeCala:
    def __init__(self, *, fail=(), limit=None):
        self.calls=0; self.calls_by_method=Counter(); self.requested=[]; self.fail=set(fail); self.limit=limit
        inv=[item("ch-org","Chalfen Ventures","Organization","e-ch-org"),item("ch-co","CHALFEN VENTURES LLP","Company","e-ch-co"),item("ot-org","Otium Capital","Organization","e-ot-org"),item("ot-co","Otium Capital","Company","e-ot-co"),item("eight","Eight Roads","Company","e-eight")]
        inv[-1]["properties"].pop("sources")
        out={"PARTICIPATES_IN_FUNDING_ROUND":[item("round","Series A","FundingRound","e-round",role="ISSUER")],
             "PARTICIPATES_IN_CORPORATE_EVENT":[item("p1","Round one","PrivateCompanyFundingRound","e-p1"),item("p2","Round two","PrivateCompanyFundingRound","e-p2"),item("mna","MNA_COMPLETED","CorporateEvent","e-mna"),item("other","MATERIAL_AGREEMENT_ANNOUNCED","CorporateEvent","e-other")],
             "OPERATES_IN_INDUSTRY":[item("industry","Hospitality","Industry","attr-i")],
             "HAS_HEADQUARTERS_IN":[item("es","Spain","Country","attr-h")],
             "HAS_DOMAIN_NAME":[item("domain","amenitiz.com","Domain","attr-d")]}
        self.data={"amen":raw("amen","Amenitiz","Company",{"incoming":{"INVESTED_IN":inv,"FOUNDED":[item("person","Founder","Person","e-founder")],"WORKS_AT":[item("product","Amenitiz","Product","e-product")]},"outgoing":out}, {"website":{"value":"amenitiz.com"}})}
        for x in inv: self.data[x["id"]]=raw(x["id"],x["name"],x["entity_type"],{"incoming":{},"outgoing":{"INVESTED_IN":[item("amen","Amenitiz","Company",x["properties"]["id"])]}})
        self.data.update({"round":raw("round","Series A","FundingRound"),"person":raw("person","Founder","Person"),"mna":raw("mna","MNA_COMPLETED","CorporateEvent")})
        if limit:
            self.data["amen"]["relationships"]["incoming"]["INVESTED_IN"]=[item(f"n{i}",f"N{i}","Company",f"e{i}") for i in range(limit)]
    async def retrieve(self,ident,**kwargs):
        self.calls+=1; self.calls_by_method["retrieve"]+=1; self.requested.append(ident)
        if ident in self.fail: raise RuntimeError("Cala down")
        return self.data[ident]
    async def introspection(self,ident):
        self.calls+=1; self.calls_by_method["introspection"]+=1
        return {"properties":[],"relationships":{"incoming":["INVESTED_IN"],"outgoing":["INVESTED_IN"]}}
    async def entities(self,name,typ):
        self.calls+=1; self.calls_by_method["entities"]+=1
        return {"entities":[{"id":"amen","name":name,"entity_type":"Company"}] if typ=="Company" and name=="Amenitiz" else []}

@pytest.fixture(params=["memory","valkey"])
def graph(request):
    client=FakeRedis()
    kv=MemoryKV() if request.param=="memory" else ValkeyKV("redis://fake",client=client)
    return GraphStore(kv),request.param,client

def run(coro): return asyncio.run(coro)
def node_keys(store):
    data=store.kv.data if isinstance(store.kv,MemoryKV) else store.kv.client.data
    return [k for k in data if ":node:" in k]

def test_expand_orientation_modes_and_sources(graph):
    store,_,_=graph; cala=FakeCala(); stats={"cala_calls":0,"excluded":Counter(),"truncated":[],"errors":[]}
    run(expand_node(store,cala,"amen",stats)); edge=store.get_edge("e-ch-co")
    assert (edge["src"],edge["dst"],edge["sources"])==("ch-co","amen",SOURCES)
    assert store.is_expanded("amen",EXPAND_KEY)
    other={"cala_calls":0,"excluded":Counter(),"truncated":[],"errors":[]}
    run(expand_node(store,FakeCala(),"amen",other,introspect=True)); assert other["cala_calls"]==2


def test_exclusions_merges_and_attributes(graph):
    store,_,_=graph; cala=FakeCala(); stats=run(load_neighborhood(store,cala,["amen"],depth=1))
    keys=node_keys(store); types=[store.get_node(k.rsplit(":",1)[-1])["type"] for k in keys]
    assert "PrivateCompanyFundingRound" not in types and "Product" not in types and "Country" not in types
    assert stats["excluded"]["PrivateCompanyFundingRound"]==2 and stats["excluded"]["Product"]==1 and stats["excluded"]["CorporateEvent:no_mna"]==1
    assert store.get_node("mna") and store.resolve("Chalfen Ventures")=="ch-co" and store.resolve("Otium Capital")=="ot-co"
    assert store.get_node("amen") and store.resolve("Amenitiz")=="amen"
    props=store.get_node("amen")["props"]
    assert props["industries"][0]["sources"]==SOURCES and props["hq"]["name"]=="Spain" and props["domain"]["name"]=="amenitiz.com"
    assert not any(e["rel"]=="OPERATES_IN_INDUSTRY" for e in store.edges_of("amen"))


def test_cached_load_and_seed_resolution(graph):
    store,_,_=graph; cala=FakeCala(); ids=run(resolve_seeds(store,cala,["Amenitiz"])); before=cala.calls
    assert run(resolve_seeds(store,cala,["Amenitiz"]))==ids and cala.calls==before
    first=run(load_neighborhood(store,cala,ids,user="a",depth=2,quota=2)); count=cala.calls
    second=run(load_neighborhood(store,cala,ids,user="a",depth=2,quota=2))
    assert cala.calls==count and second["cala_calls"]==0 and second["skipped_expanded"]>0
    assert (first["nodes"],first["edges"])==(second["nodes"],second["edges"])


def test_canonical_edge_and_missing_sources_filter(graph):
    store,_,_=graph; cala=FakeCala(); run(load_neighborhood(store,cala,["amen"],depth=1))
    edge=store.get_edge("e-ch-co"); assert (edge["src"],edge["dst"])==("ch-co","amen")
    assert len([e for e in store.edges_of("amen") if e.get("id")=="e-ch-co"])==1
    assert store.get_edge("e-eight")["sources"]==[]
    assert all(e.get("id")!="e-eight" for e,_ in store.neighbors("amen",require_sources=True))
    assert any(e.get("id")=="e-eight" for e,_ in store.neighbors("amen"))


def test_truncation_at_cala_limit(graph):
    _,backend,_=graph
    for size,expected in [(100,True),(99,False)]:
        store=GraphStore(MemoryKV() if backend=="memory" else ValkeyKV("fake",client=FakeRedis())); stats=run(load_neighborhood(store,FakeCala(limit=size),["amen"],depth=1))
        assert (store.get_node("amen").get("truncated",False)) is expected
        if expected: assert "amen" in stats["truncated"]


def test_quota_priority_and_depth():
    def setup():
        s=GraphStore(MemoryKV()); c=FakeCala(); ids=run(resolve_seeds(s,c,["Amenitiz"])); return s,c,ids
    s,c,ids=setup(); run(load_neighborhood(s,c,ids,depth=2,quota=2)); picked=[x for x in c.requested if x!="amen"]
    assert len(picked)==2 and picked==["ch-co","eight"]
    s,c,ids=setup(); run(load_neighborhood(s,c,ids,depth=2,quota=2,priority=lambda n: 100 if n["id"]=="round" else 0)); assert "round" in c.requested
    s,c,ids=setup(); run(load_neighborhood(s,c,ids,depth=1)); assert c.calls_by_method["retrieve"]==1


def test_view_isolated_and_expansion_shared(graph):
    store,_,_=graph; cala=FakeCala(); run(load_neighborhood(store,cala,["amen"],user="a",depth=2,quota=2)); prior=store.view_nodes("a")
    # otra semilla visible se suma, sin reemplazar la vista previa
    run(load_neighborhood(store,cala,["round"],user="a",depth=1)); assert prior <= store.view_nodes("a")
    run(load_neighborhood(store,cala,["person"],user="b",depth=1)); assert store.view_seeds("b")==["person"]
    before=cala.calls; run(load_neighborhood(store,cala,["amen"],user="b",depth=1)); assert cala.calls==before
    assert all(store.get_node(k.rsplit(":",1)[-1]).get("name") not in {"a", "b"} for k in node_keys(store))


def test_cala_error_does_not_mark_expanded(graph):
    store=graph[0]; cala=FakeCala(fail={"amen"}); result=run(load_neighborhood(store,cala,["amen"],depth=1))
    assert result["errors"] and result["errors"][0]["id"]=="amen" and not store.is_expanded("amen",EXPAND_KEY)


def test_preload_json_and_empty_seeds(graph,capsys):
    args=SimpleNamespace(seeds=["Amenitiz"],seeds_file=None,nordic=False,user="demo",depth=1,quota=2,introspect=False)
    store=graph[0]; cala=FakeCala(); first=run(preload.run(args,store,cala)); json.loads(capsys.readouterr().out)
    assert {"backend","user","seeds","nodes","edges","cala_calls","http_calls","store"} <= first.keys()
    second=run(preload.run(args,store,cala)); capsys.readouterr(); assert second["cala_calls"]==0
    args.seeds=["unknown"]; failed=run(preload.run(args,GraphStore(MemoryKV() if graph[1]=="memory" else ValkeyKV("fake",client=FakeRedis())),FakeCala())); capsys.readouterr(); assert failed["error"]=="no seeds resolved"


def test_valkey_cached_load_roundtrips():
    client=FakeRedis(); store=GraphStore(ValkeyKV("fake",client=client),cache_size=1000); cala=FakeCala(); run(load_neighborhood(store,cala,["amen"],depth=2,quota=2))
    client.trips=0; second=run(load_neighborhood(store,cala,["amen"],depth=2,quota=2))
    assert client.trips<=8, f"idas y vueltas observadas: {client.trips} (medición local: 0)"
    assert second["cala_calls"]==0
