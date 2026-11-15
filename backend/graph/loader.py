"""Loads the Cala neighborhood into the shared graph using BFS."""
import time
from collections import Counter

from .model import ATTRIBUTE_RELS, EXCLUDED_TYPES, REL_WHITELIST, normalize_name, node_is_expanded

EXPAND_KEY = "biz:v1"
NODE_PROPERTIES = ["name", "legal_name", "aliases", "website", "description", "founding_date", "funding_stage", "total_funding", "total_funding_units", "employee_count_range", "operational_status", "round_label", "instrument", "transaction_value", "transaction_value_units", "announcement_date", "event_date"]
LIMIT = 100
ALL_RELS = tuple(REL_WHITELIST) + tuple(ATTRIBUTE_RELS)
DEFAULT_PRIORITY = {"Company": 3, "Organization": 3, "FundingRound": 2, "Person": 1}


def _rel_request(rels):
    return {direction: {rel: {"limit": LIMIT} for rel in rels}
            for direction in ("outgoing", "incoming")}


def _item_node(item):
    return {"id": str(item["id"]), "type": item.get("entity_type", ""),
            "name": item.get("name", ""), "props": {}}


def _attribute(item):
    props = item.get("properties") or {}
    return {"id": item.get("id"), "name": item.get("name", ""),
            "sources": props.get("sources") or []}


def _props_from_retrieve(data):
    props = dict(data.get("properties") or {})
    rels = data.get("relationships") or {}
    for rel, attr in ATTRIBUTE_RELS.items():
        items = (rels.get("outgoing") or {}).get(rel) or []
        if not items:
            items = (rels.get("incoming") or {}).get(rel) or []
        if items:
            values = [_attribute(item) for item in items]
            props[attr] = values if attr == "industries" else values[0]
    return props


async def expand_node(store, cala, node_id, stats, *, introspect=False):
    calls = 0
    try:
        properties, rels = NODE_PROPERTIES, ALL_RELS
        if introspect:
            calls += 1; stats["cala_calls"] += 1; info = await cala.introspection(node_id)
            available = set(info.get("properties") or [])
            properties = [name for name in NODE_PROPERTIES if name in available]
            rel_info = info.get("relationships") or {}
            rels = tuple(rel for rel in ALL_RELS if rel in
                         set((rel_info.get("outgoing") or []) + (rel_info.get("incoming") or [])))
        request = _rel_request(rels)
        calls += 1; stats["cala_calls"] += 1
        raw = await cala.retrieve(node_id, properties=properties, relationships=request)
        anchor_id = str(raw.get("id", node_id))
        node = {"id": anchor_id, "type": raw.get("entity_type", ""),
                "name": raw.get("name", ""), "props": _props_from_retrieve(raw)}
        aliases = (node["props"].get("aliases") or {}).get("value")
        node["aliases"] = aliases if isinstance(aliases, list) and all(isinstance(x, str) for x in aliases) else []
        edges, neighbors, truncated = [], [], False
        excluded = stats["excluded"]
        relationships = raw.get("relationships") or {}
        for direction in ("incoming", "outgoing"):
            groups = relationships.get(direction) or {}
            for rel in rels:
                items = groups.get(rel) or []
                if len(items) == LIMIT:
                    truncated = True
                if rel in ATTRIBUTE_RELS:
                    continue
                for item in items:
                    typ, name = item.get("entity_type", ""), item.get("name", "")
                    if typ in EXCLUDED_TYPES:
                        excluded[typ] += 1
                        continue
                    if rel == "PARTICIPATES_IN_CORPORATE_EVENT" and not name.startswith("MNA_"):
                        excluded["CorporateEvent:no_mna"] += 1
                        continue
                    neighbors.append(_item_node(item))
                    props = item.get("properties") or {}
                    edge = {"id": props.get("id"), "src": str(item["id"] if direction == "incoming" else anchor_id),
                            "dst": str(anchor_id if direction == "incoming" else item["id"]),
                            "rel": rel, "sources": props.get("sources") or []}
                    for key in ("role", "is_lead", "valid_since", "valid_until", "event_date"):
                        if key in props: edge[key] = props[key]
                    edges.append(edge)
        canonical = store.put_expansion(node, edges, neighbors, rels=EXPAND_KEY, truncated=truncated)
        if truncated: stats["truncated"].append(canonical)
        stats["nodes"].add(canonical)
        stats["edges"].update(str(edge["id"]) for edge in edges if edge.get("id"))
        return canonical
    except Exception as exc:
        stats["errors"].append({"id": str(node_id), "error": str(exc)[:200]})
        return None


async def load_neighborhood(store, cala, seed_ids, *, user=None, depth=2, quota=15, priority=None, introspect=False):
    started = time.monotonic()
    stats = {"nodes": set(), "edges": set(), "cala_calls": 0, "skipped_expanded": 0,
             "excluded": Counter(), "truncated": [], "errors": [], "levels": []}
    canonical_seeds = store.canonical_ids(seed_ids)
    seeds = list(dict.fromkeys(canonical_seeds[str(i)] for i in seed_ids))
    reached, visited, frontier = set(seeds), set(seeds), seeds
    for level in range(max(0, depth)):
        current = list(frontier)
        fetched_nodes = store.get_nodes(current)
        for ident in current:
            node = fetched_nodes.get(ident)
            if node and node_is_expanded(node, EXPAND_KEY, store.ttl_s):
                stats["skipped_expanded"] += 1
            else:
                await expand_node(store, cala, ident, stats, introspect=introspect)
        stats["levels"].append(len(current))
        rows = store.neighbors(current, rels=REL_WHITELIST)
        candidates = {}
        for ident in current:
            for _, node in rows.get(ident, []):
                nid = node["id"]
                reached.add(nid)
                if nid not in visited: candidates[nid] = node
        visited.update(candidates)
        def sort_key(pair):
            ident, node = pair
            rank = priority(node) if priority else DEFAULT_PRIORITY.get(node.get("type"), 0)
            return (-rank, normalize_name(node.get("name", "")), ident)
        frontier = [ident for ident, _ in sorted(candidates.items(), key=sort_key)[:max(0, quota)]]
        if level + 1 >= depth: break
    # Counts traversal edges and nodes from the store, including existing ones.
    if reached:
        all_rows = store.neighbors(list(reached), rels=REL_WHITELIST)
        for row in all_rows.values():
            for edge, _ in row:
                if edge["src"] in reached and edge["dst"] in reached:
                    stats["edges"].add(str(edge["id"]))
    stats["nodes"].update(reached)
    if user is not None:
        prior = store.view_seeds(user)
        if prior:
            merged_seeds = list(dict.fromkeys(prior + seeds))
            store.set_view(user, merged_seeds, store.view_nodes(user) | reached)
        else:
            store.set_view(user, seeds, reached)
    return {"nodes": len(stats["nodes"]), "edges": len(stats["edges"]),
            "cala_calls": stats["cala_calls"], "skipped_expanded": stats["skipped_expanded"],
            "excluded": dict(stats["excluded"]), "truncated": list(dict.fromkeys(stats["truncated"])),
            "errors": stats["errors"], "seconds": time.monotonic() - started,
            "view_nodes": len(reached), "levels": stats["levels"]}


async def resolve_seeds(store, cala, names, stats=None):
    ids, calls = [], 0
    for name in names:
        found = store.resolve(name)
        if not found:
            entities = await cala.entities(name, "Company"); calls += 1
            if not entities.get("entities"):
                entities = await cala.entities(name, "Organization"); calls += 1
            choices = entities.get("entities") or []
            chosen = next((e for e in choices if normalize_name(e.get("name")) == normalize_name(name)), choices[0] if choices else None)
            if not chosen: continue
            aliases = [] if normalize_name(chosen.get("name")) == normalize_name(name) else [name]
            found = store.put_node({"id": str(chosen["id"]), "type": chosen.get("entity_type", ""),
                                    "name": chosen.get("name", ""), "aliases": aliases})
        if found not in ids: ids.append(found)
    if stats is not None: stats["cala_calls"] = stats.get("cala_calls", 0) + calls
    return ids
