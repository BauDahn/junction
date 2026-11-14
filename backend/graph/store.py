"""Almacén compartido de nodos y aristas con adaptadores de memoria y Valkey."""
import hashlib
import json
import os
import time
from collections import OrderedDict
from datetime import datetime, timezone
from .model import PREFIX, TTL_S, normalize_name, now_iso, types_compatible, website_key

class MemoryKV:
    def __init__(self): self.data, self.expiry = {}, {}
    def _live(self, k):
        if k in self.expiry and self.expiry[k] <= time.time(): self.data.pop(k, None); self.expiry.pop(k, None)
        return self.data.get(k)
    def get(self, k): return self._live(k)
    def mget(self, keys): return [self.get(k) for k in keys]
    def set(self, k, v, ttl): self.data[k] = v; self.expiry[k] = time.time() + ttl if ttl else float("inf"); return True
    def delete(self, k): self.data.pop(k, None); self.expiry.pop(k, None)
    def sadd(self, k, members, ttl):
        s = self._live(k) or set(); s.update(members); self.data[k] = s; self.expiry[k] = time.time() + ttl if ttl else float("inf")
    def srem(self, k, members):
        s = self._live(k)
        if s: s.difference_update(members)
    def smembers(self, k): return set(self._live(k) or ())
    def smembers_many(self, keys): return [self.smembers(k) for k in keys]
    def ping(self): return True
    def keys(self, pattern):
        import fnmatch
        return [k for k in list(self.data) if self._live(k) is not None and fnmatch.fnmatch(k, pattern)]
    def set_many(self, entries, ttl):
        for key, value in entries: self.set(key, value, ttl)
    def delete_many(self, keys):
        for key in keys: self.delete(key)
    def sadd_many(self, entries, ttl):
        for key, members in entries: self.sadd(key, members, ttl)
    def write_batch(self, sets=(), adds=(), deletes=()):
        self.delete_many(deletes)
        for key, value, ttl in sets: self.set(key, value, ttl)
        for key, members, ttl in adds: self.sadd(key, members, ttl)

class ValkeyKV:
    def __init__(self, url=None, client=None, timeout_s=3, connect_timeout_s=8):
        self.url, self.client, self.timeout_s, self.connect_timeout_s = url, client, timeout_s, connect_timeout_s
    def _client(self):
        if self.client is None:
            import redis
            self.client = redis.Redis.from_url(self.url, socket_connect_timeout=self.connect_timeout_s, socket_timeout=self.timeout_s, decode_responses=True)
        return self.client
    def get(self, k): return self._client().get(k)
    def mget(self, keys): return self._client().mget(keys) if keys else []
    def set(self, k, v, ttl): return self._client().set(k, v, ex=ttl)
    def delete(self, k): return self._client().delete(k)
    def sadd(self, k, members, ttl):
        self.write_batch(adds=[(k, members, ttl)])
    def srem(self, k, members):
        if members: self._client().srem(k, *members)
    def smembers(self, k): return set(self._client().smembers(k))
    def smembers_many(self, keys):
        c = self._client(); p = c.pipeline()
        for k in keys: p.smembers(k)
        return [set(s) for s in p.execute()] if keys else []
    def ping(self): return self._client().ping()
    def keys(self, pattern): return list(self._client().scan_iter(match=pattern))
    def set_many(self, entries, ttl):
        if not entries: return
        p = self._client().pipeline()
        for key, value in entries: p.set(key, value, ex=ttl)
        p.execute()
    def delete_many(self, keys):
        if keys: self._client().delete(*keys)
    def sadd_many(self, entries, ttl):
        if not entries: return
        p = self._client().pipeline()
        for key, members in entries:
            if members: p.sadd(key, *members)
            p.expire(key, ttl)
        p.execute()
    def write_batch(self, sets=(), adds=(), deletes=()):
        if not sets and not adds and not deletes: return
        p = self._client().pipeline()
        for key in deletes: p.delete(key)
        for key, value, ttl in sets: p.set(key, value, ex=ttl)
        for key, members, ttl in adds:
            if members: p.sadd(key, *members)
            p.expire(key, ttl)
        p.execute()

def _json(raw): return json.loads(raw) if raw else None
def _dump(value): return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
def _nonempty(v): return v is not None and v != "" and v != [] and v != {}
def _sources(a, b):
    out, seen = [], set()
    for item in list(a or []) + list(b or []):
        key = tuple(item.get(x) for x in ("name", "document", "date")) if isinstance(item, dict) else (str(item),)
        if key not in seen: seen.add(key); out.append(item)
    return out

class GraphStore:
    def __init__(self, kv, ttl_s=TTL_S, prefix=PREFIX, local_ttl_s=0):
        self.kv, self.ttl_s, self.prefix, self.local_ttl_s = kv, ttl_s, prefix, local_ttl_s
        self._local, self._local_max = OrderedDict(), 2048
    def _cache_get(self, key):
        if not self.local_ttl_s: return None
        item = self._local.get(key)
        if not item: return None
        if item[0] <= time.monotonic(): self._local.pop(key, None); return None
        self._local.move_to_end(key)
        return item[1]
    def _cache_set(self, key, value):
        if not self.local_ttl_s: return
        self._local[key] = (time.monotonic() + self.local_ttl_s, value)
        self._local.move_to_end(key)
        while len(self._local) > self._local_max: self._local.popitem(last=False)
    def _invalidate(self): self._local.clear()
    def _k(self, kind, ident): return f"{self.prefix}{kind}:{ident}"
    def _put_json(self, k, value): self.kv.set(k, _dump(value), self.ttl_s)
    def canonical_id(self, node_id):
        return self.canonical_ids([str(node_id)])[str(node_id)]
    def canonical_ids(self, ids):
        originals = list(dict.fromkeys(str(i) for i in ids)); current = {i:i for i in originals}
        pending = originals[:]
        while pending:
            keys = [self._k("alias:id", current[i]) for i in pending]
            vals = self.kv.mget(keys)
            changed = []
            for ident, raw in zip(pending, vals):
                if raw and raw != current[ident]: current[ident] = raw; changed.append(ident)
            # Solo se vuelve a consultar una cadena que realmente avanzó.
            pending = changed
        return current
    def _read_nodes_canonical(self, canonical):
        vals = self.kv.mget([self._k("node", i) for i in canonical.values()])
        return {requested: _json(raw) for requested, raw in zip(canonical, vals) if raw}
    def get_node(self, node_id): return self.get_nodes([node_id]).get(str(node_id))
    def get_nodes(self, ids):
        requested = list(dict.fromkeys(str(i) for i in ids))
        mapped = self.canonical_ids(requested)
        result, missing = {}, []
        for ident in requested:
            cached = self._cache_get(("node", mapped[ident]))
            if cached is None: missing.append(ident)
            else: result[ident] = cached
        if missing:
            subset = {i:mapped[i] for i in missing}; found = self._read_nodes_canonical(subset)
            result.update(found)
            for i, n in found.items(): self._cache_set(("node", mapped[i]), n)
        return result
    def get_edge(self, edge_id):
        cache_key = ("edge", edge_id); cached = self._cache_get(cache_key)
        if cached is not None: return cached
        value = _json(self.kv.get(self._k("edge", edge_id)))
        if value is not None: self._cache_set(cache_key, value)
        return value
    def edges_of(self, node_id, require_sources=False):
        current = self.canonical_id(node_id); cache_key = ("adj", current)
        ids = self._cache_get(cache_key)
        if ids is None:
            ids = sorted(self.kv.smembers(self._k("adj", current))); self._cache_set(cache_key, ids)
        edges, missing = {}, []
        for eid in ids:
            cached = self._cache_get(("edge", eid))
            if cached is None: missing.append(eid)
            else: edges[eid] = cached
        if missing:
            values = self.kv.mget([self._k("edge", i) for i in missing])
            for eid, raw in zip(missing, values):
                value = _json(raw)
                if value is not None: edges[eid] = value; self._cache_set(("edge", eid), value)
        return sorted([e for e in edges.values() if e and (not require_sources or e.get("sources"))], key=lambda e: e["id"])
    def neighbors(self, node_id, rels=None, require_sources=False):
        current = self.canonical_id(node_id); edges = self.edges_of(current, require_sources)
        edges = [e for e in edges if rels is None or e.get("rel") in rels]
        endpoint_ids = [x for e in edges for x in (e["src"], e["dst"])]
        canonical = self.canonical_ids(endpoint_ids)
        pairs = [(e, canonical[e["dst"]] if canonical[e["src"]] == current else canonical[e["src"]]) for e in edges]
        nodes = self.get_nodes([n for _, n in pairs]); return [(e, nodes[n]) for e, n in pairs if n in nodes]
    def resolve(self, name):
        norm = normalize_name(name)
        ids = _json(self.kv.get(self._k("alias", norm))) or []
        nodes = self.get_nodes(ids)
        chosen = next((i for i in ids if nodes.get(i, {}).get("type") == "Company"), next((i for i in ids if nodes.get(i, {}).get("type") == "Organization"), ids[0] if ids else None))
        return nodes[chosen]["id"] if chosen in nodes else None
    def _aliases(self, node):
        return list(dict.fromkeys([node.get("name", ""), *(node.get("aliases") or [])] if node.get("name") else (node.get("aliases") or [])))
    def _website(self, node): return website_key(((node.get("props") or {}).get("website") or {}).get("value"))
    def _merge(self, existing, incoming, canonical):
        other = incoming if incoming["id"] != existing["id"] else None
        result = dict(existing)
        result["id"] = canonical
        result["type"] = "Company" if "Company" in (existing.get("type"), incoming.get("type")) else existing.get("type", incoming.get("type"))
        result["name"] = (existing if existing["id"] == canonical else incoming).get("name", "")
        aliases = (existing.get("aliases") or []) + (incoming.get("aliases") or [])
        for n in (existing.get("name"), incoming.get("name")):
            if n and n != result["name"]: aliases.append(n)
        result["aliases"] = list(dict.fromkeys(n for n in aliases if n and n != result["name"]))
        result["merged_ids"] = list(dict.fromkeys((existing.get("merged_ids") or []) + (incoming.get("merged_ids") or []) + ([other["id"]] if other else [])))
        props = dict(existing.get("props") or {})
        props.update({k:v for k,v in (incoming.get("props") or {}).items() if _nonempty(v)}); result["props"] = props
        exp = dict(existing.get("expanded") or {}); exp.update({k:v for k,v in (incoming.get("expanded") or {}).items() if v > exp.get(k, "")}); result["expanded"] = exp
        result["truncated"] = bool(existing.get("truncated") or incoming.get("truncated"))
        result["loaded_at"] = max(existing.get("loaded_at", ""), incoming.get("loaded_at") or now_iso())
        return result
    def put_node(self, node):
        incoming = dict(node); incoming["id"] = str(node["id"]); incoming.setdefault("loaded_at", now_iso()); incoming.setdefault("aliases", []); incoming.setdefault("props", {}); incoming.setdefault("expanded", {})
        name = incoming.get("name") or ""; norm = normalize_name(name)
        id_map = self.canonical_ids([incoming["id"]]); old_id = id_map[incoming["id"]]
        existing_raw = self.kv.mget([self._k("node", old_id)])[0]
        existing = _json(existing_raw)
        if existing:
            canonical = old_id
        else:
            alias_raw = self.kv.mget([self._k("alias", norm)])[0] if norm else None
            candidates = _json(alias_raw) or []
            candidate_ids = self.canonical_ids(candidates)
            candidate_nodes = self.kv.mget([self._k("node", candidate_ids[i]) for i in candidates])
            compatible = []
            for cid, raw in zip(candidates, candidate_nodes):
                cid = candidate_ids[cid]; n = _json(raw)
                if not n or not types_compatible(n.get("type"), incoming.get("type")): continue
                a, b = self._website(n), self._website(incoming)
                if a and b and a != b: continue
                compatible.append((cid, n))
            if compatible:
                cid, existing = compatible[0]
                canonical = incoming["id"] if incoming.get("type") == "Company" and existing.get("type") != "Company" else cid
            else: canonical = incoming["id"]
        if existing:
            merged = self._merge(existing, incoming, canonical)
        else: merged = incoming; merged["id"] = canonical
        old_ids = [i for i in dict.fromkeys(([existing.get("id")] if existing else []) + [incoming["id"]] + (merged.get("merged_ids") or [])) if i and i != canonical]
        old_adj = self.kv.smembers_many([self._k("adj", i) for i in old_ids]) if old_ids else []
        edge_ids = sorted(set().union(*old_adj) if old_adj else set())
        edge_raw = self.kv.mget([self._k("edge", i) for i in edge_ids])
        edge_sets, adj_adds = [], {}
        for eid, raw in zip(edge_ids, edge_raw):
            edge = _json(raw)
            if not edge: continue
            if edge.get("src") in old_ids: edge["src"] = canonical
            if edge.get("dst") in old_ids: edge["dst"] = canonical
            edge_sets.append((self._k("edge", eid), _dump(edge), self.ttl_s))
            adj_adds.setdefault(self._k("adj", canonical), set()).add(eid)
        names = list(dict.fromkeys(self._aliases(merged) + self._aliases(existing or {}) + self._aliases(incoming)))
        alias_norms = list(dict.fromkeys(normalize_name(n) for n in names if normalize_name(n)))
        alias_keys = [self._k("alias", n) for n in alias_norms]
        alias_values = self.kv.mget(alias_keys)
        alias_lists = [_json(raw) or [] for raw in alias_values]
        alias_ids = self.canonical_ids([i for values in alias_lists for i in values])
        sets = [(self._k("node", canonical), _dump(merged), self.ttl_s)] + edge_sets
        for ident in old_ids: sets.append((self._k("alias:id", ident), canonical, self.ttl_s))
        for key, arr in zip(alias_keys, alias_lists):
            arr = [canonical if x in old_ids or alias_ids[x] == canonical else x for x in arr]
            if canonical not in arr: arr.append(canonical)
            sets.append((key, _dump(list(dict.fromkeys(arr))), self.ttl_s))
        adds = [(key, sorted(members), self.ttl_s) for key, members in adj_adds.items()]
        deletes = [self._k("node", i) for i in old_ids] + [self._k("adj", i) for i in old_ids]
        self.kv.write_batch(sets, adds, deletes); self._invalidate()
        return canonical
    def put_edge(self, edge):
        e = dict(edge); mapped = self.canonical_ids([e["src"], e["dst"]]); e["src"], e["dst"] = mapped[str(e["src"])], mapped[str(e["dst"])]
        if e["src"] == e["dst"]: return None
        e["sources"] = e.get("sources") or []; e.setdefault("loaded_at", now_iso())
        if not e.get("id"):
            digest = hashlib.sha1("|".join(str(e.get(k, "")) for k in ("src", "rel", "dst", "role")).encode()).hexdigest()[:16]; e["id"] = "e:" + digest
        old = self.get_edge(e["id"])
        if old:
            old.update({k:v for k,v in e.items() if k != "sources" and _nonempty(v)}); old["sources"] = _sources(old.get("sources"), e["sources"]); e = old
        adds = [(self._k("adj", i), [e["id"]], self.ttl_s) for i in dict.fromkeys((e["src"], e["dst"]))]
        self.kv.write_batch([(self._k("edge", e["id"]), _dump(e), self.ttl_s)], adds); self._invalidate()
        return e["id"]
    def view_seeds(self, user):
        ids = _json(self.kv.get(self._k("view", f"{user}:seeds"))) or []; mapped = self.canonical_ids(ids)
        return [mapped[str(i)] for i in ids]
    def view_nodes(self, user):
        ids = self.kv.smembers(self._k("view", f"{user}:nodes")); return set(self.canonical_ids(ids).values())
    def set_view(self, user, seeds, nodes):
        ids = list(dict.fromkeys([str(i) for i in seeds])); nodes = list(dict.fromkeys([str(i) for i in nodes]))
        mapped = self.canonical_ids(ids + nodes); key = self._k("view", f"{user}:nodes")
        self.kv.write_batch([(self._k("view", f"{user}:seeds"), _dump([mapped[i] for i in ids]), self.ttl_s)], [(key, [mapped[i] for i in nodes], self.ttl_s)], [key]); self._invalidate()
    def add_to_view(self, user, node_ids):
        ids = list(dict.fromkeys(str(i) for i in node_ids)); mapped = self.canonical_ids(ids)
        self.kv.sadd(self._k("view", f"{user}:nodes"), list(dict.fromkeys(mapped.values())), self.ttl_s); self._invalidate()
    def distance(self, sources, target, max_depth=3, within=None):
        ids = list(dict.fromkeys([str(x) for x in sources] + [str(target)])); mapped = self.canonical_ids(ids)
        target = mapped[str(target)]; start = {mapped[str(s)] for s in sources}
        if target in start: return 0
        if not self.get_nodes([target]): return None
        within_ids = set(self.canonical_ids(within).values()) if within is not None else None
        seen = set(start); frontier = start
        for depth in range(1, max_depth + 1):
            keys = [self._k("adj", n) for n in sorted(frontier)]; groups = self.kv.smembers_many(keys)
            edge_ids = sorted(set().union(*groups) if groups else set()); vals = self.kv.mget([self._k("edge", i) for i in edge_ids])
            nxt = set()
            decoded = [_json(raw) for raw in vals]
            endpoint_ids = [x for edge in decoded if edge for x in (edge["src"], edge["dst"])]
            canonical = self.canonical_ids(endpoint_ids)
            for e in decoded:
                if not e: continue
                a, b = canonical[e["src"]], canonical[e["dst"]]
                if a in frontier: nxt.add(b)
                if b in frontier: nxt.add(a)
            nxt -= seen
            if within_ids is not None: nxt = {n for n in nxt if n == target or n in within_ids}
            if target in nxt: return depth
            seen |= nxt; frontier = nxt
            if not frontier: break
        return None
    def is_expanded(self, node_id, key, max_age_s=None):
        node = self.get_node(node_id); date = (node or {}).get("expanded", {}).get(key)
        if not date: return False
        try:
            parsed = datetime.fromisoformat(date)
            if parsed.tzinfo is None: parsed = parsed.replace(tzinfo=timezone.utc)
            age = (datetime.now(timezone.utc) - parsed.astimezone(timezone.utc)).total_seconds()
        except (ValueError, TypeError): return False
        return age < (self.ttl_s if max_age_s is None else max_age_s)
    def mark_expanded(self, node_id, key, truncated=False):
        node = self.get_node(node_id)
        if not node: return
        node.setdefault("expanded", {})[key] = now_iso(); node["truncated"] = bool(node.get("truncated") or truncated); self._put_json(self._k("node", node["id"]), node)
        self._invalidate()
    @staticmethod
    def rels_key(rels): return ",".join(sorted(set(rels or ())))
    def put_expansion(self, node_id, rels, nodes=(), edges=(), truncated=False):
        """Guarda los elementos recibidos y marca el conjunto de relaciones como expandido."""
        saved = [self.put_node(n) for n in nodes]
        for edge in edges: self.put_edge(edge)
        self.mark_expanded(node_id, self.rels_key(rels), truncated=truncated)
        return saved
    def stats(self): return {kind: len(self.kv.keys(self._k(kind, "*"))) for kind in ("node", "edge")}

_STORE = None
def _timeout_env(name, default):
    try: return max(0.1, float(os.getenv(name, default)))
    except (TypeError, ValueError): return default

def reset_store():
    global _STORE
    _STORE = None
def get_store():
    global _STORE
    if _STORE is not None: return _STORE
    from canonizador.cache import load_env
    load_env(); url = (os.getenv("VALKEY_URL") or "").strip()
    if url:
        kv = ValkeyKV(url, timeout_s=_timeout_env("VALKEY_TIMEOUT", 3), connect_timeout_s=_timeout_env("VALKEY_CONNECT_TIMEOUT", 8))
        try: connected = kv.ping()
        except Exception: connected = False
        if connected: _STORE = GraphStore(kv, local_ttl_s=30); _STORE.backend = "valkey"; return _STORE
    _STORE = GraphStore(MemoryKV()); _STORE.backend = "memory"; return _STORE
