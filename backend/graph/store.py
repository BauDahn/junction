"""Almacén compartido de nodos y aristas con adaptadores de memoria y Valkey."""
import hashlib
import json
import os
import time
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
        c = self._client()
        if members: c.sadd(k, *members)
        c.expire(k, ttl)
    def srem(self, k, members):
        if members: self._client().srem(k, *members)
    def smembers(self, k): return set(self._client().smembers(k))
    def smembers_many(self, keys):
        c = self._client(); p = c.pipeline()
        for k in keys: p.smembers(k)
        return [set(s) for s in p.execute()] if keys else []
    def ping(self): return self._client().ping()
    def keys(self, pattern): return list(self._client().scan_iter(match=pattern))

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
    def _k(self, kind, ident): return f"{self.prefix}{kind}:{ident}"
    def _put_json(self, k, value): self.kv.set(k, _dump(value), self.ttl_s)
    def canonical_id(self, node_id):
        seen, cur = set(), str(node_id)
        while cur not in seen:
            seen.add(cur); nxt = self.kv.get(self._k("alias:id", cur))
            if not nxt: break
            cur = nxt
        return cur
    def get_node(self, node_id): return _json(self.kv.get(self._k("node", self.canonical_id(node_id))))
    def get_nodes(self, ids):
        canonical = [self.canonical_id(i) for i in ids]
        vals = self.kv.mget([self._k("node", i) for i in canonical])
        return {i: _json(v) for i, v in zip(canonical, vals) if v}
    def get_edge(self, edge_id): return _json(self.kv.get(self._k("edge", edge_id)))
    def edges_of(self, node_id, require_sources=False):
        ids = sorted(self.kv.smembers(self._k("adj", self.canonical_id(node_id))))
        found = [_json(v) for v in self.kv.mget([self._k("edge", i) for i in ids])]
        return sorted([e for e in found if e and (not require_sources or e.get("sources"))], key=lambda e: e["id"])
    def neighbors(self, node_id, rels=None, require_sources=False):
        current = self.canonical_id(node_id); edges = self.edges_of(current, require_sources)
        edges = [e for e in edges if rels is None or e.get("rel") in rels]
        pairs = [(e, self.canonical_id(e["dst"] if self.canonical_id(e["src"]) == current else e["src"])) for e in edges]
        nodes = self.get_nodes([n for _, n in pairs]); return [(e, nodes[n]) for e, n in pairs if n in nodes]
    def resolve(self, name):
        norm = normalize_name(name)
        ids = _json(self.kv.get(self._k("alias", norm))) or []
        nodes = self.get_nodes(ids)
        return next((i for i in ids if nodes.get(i, {}).get("type") == "Company"), next((i for i in ids if nodes.get(i, {}).get("type") == "Organization"), ids[0] if ids else None))
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
        old_id = self.canonical_id(incoming["id"]); existing = self.get_node(old_id)
        if existing:
            canonical = old_id
        else:
            candidates = _json(self.kv.get(self._k("alias", norm))) or [] if norm else []
            compatible = []
            for cid in candidates:
                n = self.get_node(cid)
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
            self._put_json(self._k("node", canonical), merged)
            for old in dict.fromkeys((existing["id"], incoming["id"])):
                if old != canonical and self.kv.smembers(self._k("adj", old)):
                    self._repoint(old, canonical, merged)
        else: merged = incoming; merged["id"] = canonical; self._put_json(self._k("node", canonical), merged)
        for nm in self._aliases(merged):
            key = normalize_name(nm)
            if not key: continue
            arr = _json(self.kv.get(self._k("alias", key))) or []
            arr = [canonical if self.canonical_id(x) == canonical else x for x in arr]
            if canonical not in arr: arr.append(canonical)
            self._put_json(self._k("alias", key), list(dict.fromkeys(arr)))
        for mid in merged.get("merged_ids", []): self.kv.set(self._k("alias:id", mid), canonical, self.ttl_s)
        return canonical
    def _repoint(self, old, new, merged):
        edge_ids = sorted(self.kv.smembers(self._k("adj", old)))
        for eid in edge_ids:
            edge = self.get_edge(eid)
            if edge:
                if edge.get("src") == old: edge["src"] = new
                if edge.get("dst") == old: edge["dst"] = new
                self._put_json(self._k("edge", eid), edge); self.kv.sadd(self._k("adj", new), [eid], self.ttl_s)
        self.kv.delete(self._k("adj", old)); self.kv.delete(self._k("node", old)); self.kv.set(self._k("alias:id", old), new, self.ttl_s)
        for key in self.kv.keys(self._k("alias", "*")):
            if key.startswith(self._k("alias:id", "")): continue
            arr = _json(self.kv.get(key)) or []
            if old in arr: self._put_json(key, list(dict.fromkeys(new if x == old else x for x in arr)))
    def put_edge(self, edge):
        e = dict(edge); e["src"] = self.canonical_id(e["src"]); e["dst"] = self.canonical_id(e["dst"])
        if e["src"] == e["dst"]: return None
        e["sources"] = e.get("sources") or []; e.setdefault("loaded_at", now_iso())
        if not e.get("id"):
            digest = hashlib.sha1("|".join(str(e.get(k, "")) for k in ("src", "rel", "dst", "role")).encode()).hexdigest()[:16]; e["id"] = "e:" + digest
        old = self.get_edge(e["id"])
        if old:
            old.update({k:v for k,v in e.items() if k != "sources" and _nonempty(v)}); old["sources"] = _sources(old.get("sources"), e["sources"]); e = old
        self._put_json(self._k("edge", e["id"]), e)
        self.kv.sadd(self._k("adj", e["src"]), [e["id"]], self.ttl_s); self.kv.sadd(self._k("adj", e["dst"]), [e["id"]], self.ttl_s)
        return e["id"]
    def view_seeds(self, user): return [self.canonical_id(i) for i in (_json(self.kv.get(self._k("view", f"{user}:seeds"))) or [])]
    def view_nodes(self, user): return {self.canonical_id(i) for i in self.kv.smembers(self._k("view", f"{user}:nodes"))}
    def set_view(self, user, seeds, nodes):
        self._put_json(self._k("view", f"{user}:seeds"), list(dict.fromkeys(seeds))); key = self._k("view", f"{user}:nodes"); self.kv.delete(key); self.kv.sadd(key, list(dict.fromkeys(nodes)), self.ttl_s)
    def add_to_view(self, user, node_ids): self.kv.sadd(self._k("view", f"{user}:nodes"), list(dict.fromkeys(node_ids)), self.ttl_s)
    def distance(self, sources, target, max_depth=3, within=None):
        target = self.canonical_id(target); start = {self.canonical_id(s) for s in sources}
        if target in start: return 0
        if not self.get_node(target): return None
        seen = set(start); frontier = start
        for depth in range(1, max_depth + 1):
            keys = [self._k("adj", n) for n in sorted(frontier)]; groups = self.kv.smembers_many(keys)
            edge_ids = sorted(set().union(*groups) if groups else set()); vals = self.kv.mget([self._k("edge", i) for i in edge_ids])
            nxt = set()
            for raw in vals:
                e = _json(raw)
                if not e: continue
                a, b = self.canonical_id(e["src"]), self.canonical_id(e["dst"])
                for n in frontier:
                    if a == n: nxt.add(b)
                    if b == n: nxt.add(a)
            nxt -= seen
            if within is not None: nxt = {n for n in nxt if n == target or n in {self.canonical_id(x) for x in within}}
            if target in nxt: return depth
            seen |= nxt; frontier = nxt
            if not frontier: break
        return None
    def is_expanded(self, node_id, key, max_age_s=None):
        node = self.get_node(node_id); date = (node or {}).get("expanded", {}).get(key)
        if not date: return False
        from datetime import datetime
        try: age = (datetime.now().astimezone() - datetime.fromisoformat(date)).total_seconds()
        except (ValueError, TypeError): return False
        return age < (self.ttl_s if max_age_s is None else max_age_s)
    def mark_expanded(self, node_id, key, truncated=False):
        node = self.get_node(node_id)
        if not node: return
        node.setdefault("expanded", {})[key] = now_iso(); node["truncated"] = bool(node.get("truncated") or truncated); self._put_json(self._k("node", node["id"]), node)
    def stats(self): return {kind: len(self.kv.keys(self._k(kind, "*"))) for kind in ("node", "edge")}

_STORE = None
def reset_store():
    global _STORE
    _STORE = None
def get_store():
    global _STORE
    if _STORE is not None: return _STORE
    try:
        from canonizador.cache import load_env, _int_env
        load_env(); url = (os.getenv("VALKEY_URL") or "").strip()
        if url:
            kv = ValkeyKV(url, timeout_s=_int_env("VALKEY_TIMEOUT", 3), connect_timeout_s=_int_env("VALKEY_CONNECT_TIMEOUT", 8))
            if kv.ping(): _STORE = GraphStore(kv, local_ttl_s=30); _STORE.backend = "valkey"; return _STORE
    except Exception: pass
    _STORE = GraphStore(MemoryKV()); _STORE.backend = "memory"; return _STORE
