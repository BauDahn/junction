import asyncio
from collections import Counter
import pytest

from graph.loader import EXPAND_KEY, expand_node, load_neighborhood, resolve_seeds
from graph.model import REL_WHITELIST
from graph.store import GraphStore, MemoryKV


class FakeCala:
    def __init__(self):
        self.calls = 0
        self.data = {
            "amen": {"id": "amen", "name": "Amenitiz", "entity_type": "Company", "properties": {},
                     "relationships": {"incoming": {"INVESTED_IN": [self.item("fund", "Chalfen Ventures", "Organization", "edge1")]}, "outgoing": {}}},
            "fund": {"id": "fund", "name": "Chalfen Ventures", "entity_type": "Organization", "properties": {},
                     "relationships": {"outgoing": {"INVESTED_IN": [self.item("amen", "Amenitiz", "Company", "edge1")]}, "incoming": {}}},
        }

    @staticmethod
    def item(ident, name, typ, edge):
        return {"id": ident, "name": name, "entity_type": typ,
                "properties": {"id": edge, "sources": [{"name": "Cala", "document": "d", "date": "2026"}]}}

    async def retrieve(self, ident, **kwargs):
        self.calls += 1
        return self.data[ident]

    async def introspection(self, ident):
        self.calls += 1
        return {"properties": [], "relationships": {"incoming": ["INVESTED_IN"], "outgoing": ["INVESTED_IN"]}}

    async def entities(self, name, typ):
        self.calls += 1
        return {"entities": [{"id": "amen", "name": "Amenitiz", "entity_type": "Company"}] if typ == "Company" else []}


@pytest.mark.parametrize("introspect,expected", [(False, 1), (True, 2)])
def test_expansion_modes_and_edge_orientation(introspect, expected):
    graph, cala = GraphStore(MemoryKV()), FakeCala()
    stats = {"cala_calls": 0, "excluded": Counter(), "truncated": [], "errors": []}
    asyncio.run(expand_node(graph, cala, "amen", stats, introspect=introspect))
    assert stats["cala_calls"] == cala.calls == expected
    edge = graph.get_edge("edge1")
    assert (edge["src"], edge["dst"]) == ("fund", "amen")
    assert edge["sources"][0]["name"] == "Cala"
    assert graph.is_expanded("amen", EXPAND_KEY)


def test_second_bfs_is_cached_and_resolve_seed_is_cached():
    graph, cala = GraphStore(MemoryKV()), FakeCala()
    ids = asyncio.run(resolve_seeds(graph, cala, ["Amenitiz"]))
    calls = cala.calls
    assert asyncio.run(resolve_seeds(graph, cala, ["Amenitiz"])) == ids
    assert cala.calls == calls
    first = asyncio.run(load_neighborhood(graph, cala, ids, user="a", depth=2, quota=2))
    calls = cala.calls
    second = asyncio.run(load_neighborhood(graph, cala, ids, user="a", depth=2, quota=2))
    assert cala.calls == calls and second["cala_calls"] == 0
    assert first["nodes"] == second["nodes"] and first["edges"] == second["edges"]
    assert second["skipped_expanded"] > 0
    assert graph.view_seeds("a") == ids and graph.view_nodes("a") == {"amen", "fund"}
