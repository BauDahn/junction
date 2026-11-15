"""Almacén compartido de nodos y aristas con adaptadores de memoria y Valkey."""
import hashlib
import json
import os
import time
from collections import OrderedDict
from datetime import datetime, timezone
from .model import PREFIX, TTL_S, normalize_name, now_iso, rels_key, node_is_expanded, types_compatible, website_key

class MemoryKV:
    def __init__(self): self.data, self.expiry = {}, {}
    def _live(self, k):
        if k in self.expiry and self.expiry[k] <= time.time(): self.data.pop(k, None); self.expiry.pop(k, None)
        return self.data.get(k)
    def get(self, k): return self._live(k)
    def mget(self, keys): return [self.get(k) for k in keys]
    def read_batch(self, gets=(), sets=()): return self.mget(gets), [self.smembers(k) for k in sets]
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
    def read_batch(self, gets=(), sets=()):
        if not gets and not sets: return [], []
        pipe = self._client().pipeline()
        for key in gets: pipe.get(key)
        for key in sets: pipe.smembers(key)
        result = pipe.execute()
        return result[:len(gets)], [set(value) for value in result[len(gets):]]
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
    def __init__(self, kv, ttl_s=TTL_S, prefix=PREFIX, cache_size=0, cache_ttl_s=30):
        self.kv, self.ttl_s, self.prefix = kv, ttl_s, prefix
        self.cache_ttl_s = cache_ttl_s
        self._local, self._local_max = OrderedDict(), cache_size
    def _cache_get(self, key):
        if not self.cache_ttl_s or not self._local_max: return None
        item = self._local.get(key)
        if not item: return None
        if item[0] <= time.monotonic(): self._local.pop(key, None); return None
        self._local.move_to_end(key)
        return item[1]
    def _cache_set(self, key, value):
        if not self.cache_ttl_s or not self._local_max: return
        if not self._local_max: return
        self._local[key] = (time.monotonic() + self.cache_ttl_s, value)
        self._local.move_to_end(key)
        while len(self._local) > self._local_max: self._local.popitem(last=False)
    def _invalidate(self): self._local.clear()
    def _cache_written(self, sets=(), adds=(), deletes=()):
        for key in deletes:
            kind, _, ident = key[len(self.prefix):].partition(":")
            self._local.pop((kind, ident), None)
        for key, value, _ in sets:
            kind, _, ident = key[len(self.prefix):].partition(":")
            if kind in ("node", "edge"):
                self._cache_set((kind, ident), _json(value))
            elif kind == "alias:id":
                self._cache_set(("alias-id", ident), value)
        for key, members, _ in adds:
            kind, _, ident = key[len(self.prefix):].partition(":")
            if kind == "adj":
                current = set(self._cache_get(("adj", ident)) or ())
                current.update(members)
                self._cache_set(("adj", ident), sorted(current))
        for key, _, _ in sets:
            if key.startswith(self._k("alias:id", "")):
                ident = key[len(self._k("alias:id", "")):]
                self._local.pop(("node", ident), None)
    def _k(self, kind, ident): return f"{self.prefix}{kind}:{ident}"
    def _put_json(self, k, value): self.kv.set(k, _dump(value), self.ttl_s)
    def canonical_id(self, node_id):
        return self.canonical_ids([str(node_id)])[str(node_id)]
    def canonical_ids(self, ids):
        originals = list(dict.fromkeys(str(i) for i in ids)); current = {i:i for i in originals}
        pending = originals[:]
        while pending:
            uncached = [i for i in pending if self._cache_get(("alias-id", current[i])) is None]
            vals = self.kv.mget([self._k("alias:id", current[i]) for i in uncached])
            resolved = {i: self._cache_get(("alias-id", current[i])) for i in pending if i not in uncached}
            resolved.update({i: raw or current[i] for i, raw in zip(uncached, vals)})
            for i, value in resolved.items():
                self._cache_set(("alias-id", current[i]), value)
            changed = []
            for ident in pending:
                raw = resolved[ident]
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
        if isinstance(node_id, str):
            return self.neighbors([node_id], rels, require_sources)[str(node_id)]
        requested = list(dict.fromkeys(str(value) for value in node_id))
        canonical = self.canonical_ids(requested)
        currents = list(dict.fromkeys(canonical[value] for value in requested))
        groups, missing_adj = [], []
        for value in currents:
            cached = self._cache_get(("adj", value))
            groups.append(set(cached) if cached is not None else None)
            if cached is None:
                missing_adj.append(value)
        fetched_groups = self.kv.smembers_many([self._k("adj", value) for value in missing_adj])
        fetched_map = dict(zip(missing_adj, fetched_groups))
        for index, value in enumerate(currents):
            if groups[index] is None:
                groups[index] = fetched_map[value]
                self._cache_set(("adj", value), sorted(groups[index]))
        per_current = {value: set(group) for value, group in zip(currents, groups)}
        edge_ids = sorted(set().union(*per_current.values()) if per_current else set())
        edge_map = {}
        missing_edges = []
        for ident in edge_ids:
            cached = self._cache_get(("edge", ident))
            if cached is None:
                missing_edges.append(ident)
            else:
                edge_map[ident] = cached
        edge_values = self.kv.mget([self._k("edge", value) for value in missing_edges])
        for ident, raw in zip(missing_edges, edge_values):
            edge = _json(raw)
            if edge:
                edge_map[ident] = edge
                self._cache_set(("edge", ident), edge)
        neighbor_ids = set()
        rows = {}
        for requested_id in requested:
            current = canonical[requested_id]
            rows[requested_id] = []
            for ident in sorted(per_current.get(current, ())):
                edge = edge_map.get(ident)
                if not edge or (require_sources and not edge.get("sources")):
                    continue
                if rels is not None and edge.get("rel") not in rels:
                    continue
                neighbor = edge["dst"] if edge["src"] == current else edge["src"]
                rows[requested_id].append((edge, neighbor))
                neighbor_ids.add(neighbor)
        missing = [value for value in sorted(neighbor_ids) if self._cache_get(("node", value)) is None]
        fetched = self.kv.mget([self._k("node", value) for value in missing])
        nodes = {value: _json(raw) for value, raw in zip(missing, fetched) if raw}
        for value, found in nodes.items():
            self._cache_set(("node", value), found)
        nodes.update({value: self._cache_get(("node", value)) for value in neighbor_ids
                      if self._cache_get(("node", value)) is not None})
        return {value: [(edge, nodes[neighbor]) for edge, neighbor in pairs if nodes.get(neighbor)]
                for value, pairs in rows.items()}
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
    def _apply(self, nodes, edges, expand=None):
        incoming = []
        for node in nodes:
            value = dict(node)
            value["id"] = str(value["id"])
            value.setdefault("loaded_at", now_iso())
            value.setdefault("aliases", [])
            value.setdefault("props", {})
            value.setdefault("expanded", {})
            incoming.append(value)
        edge_values = [dict(edge) for edge in edges]
        ids = list(dict.fromkeys([n["id"] for n in incoming] +
              [str(x) for e in edge_values for x in (e["src"], e["dst"])]))
        names = list(dict.fromkeys(n for value in incoming for n in self._aliases(value)))
        names_norm = list(dict.fromkeys(normalize_name(n) for n in names if normalize_name(n)))
        edge_ids = [str(e["id"]) for e in edge_values if e.get("id")]
        keys = ([self._k("node", i) for i in ids] + [self._k("alias:id", i) for i in ids] +
                [self._k("alias", n) for n in names_norm] + [self._k("edge", i) for i in edge_ids])
        vals, initial_adj = self.kv.read_batch(gets=keys, sets=[self._k("adj", i) for i in ids])
        raw = dict(zip(keys, vals))
        adj_by_id = dict(zip(ids, initial_adj))
        mapped = {i: raw.get(self._k("alias:id", i)) or i for i in ids}
        candidates = list(dict.fromkeys(x for n in names_norm for x in (_json(raw.get(self._k("alias", n))) or [])))
        missing = [i for i in candidates if self._k("node", mapped.get(i, i)) not in raw]
        candidate_ids = list(dict.fromkeys(candidates))
        if missing or any(i not in adj_by_id for i in candidate_ids):
            extra, candidate_adj = self.kv.read_batch(
                gets=[self._k("node", i) for i in missing],
                sets=[self._k("adj", i) for i in candidate_ids])
            raw.update(zip([self._k("node", i) for i in missing], extra))
            adj_by_id.update(zip(candidate_ids, candidate_adj))
        work_nodes = {}
        for ident in set(ids + candidates):
            value = _json(raw.get(self._k("node", mapped.get(ident, ident))))
            if value: work_nodes[mapped.get(ident, ident)] = value
        canonical = dict(mapped)
        touched_aliases = {n: list(_json(raw.get(self._k("alias", n))) or []) for n in names_norm}
        node_sets, deletes, alias_id_sets, adj_adds = {}, [], {}, {}
        old_ids = set()
        repoints = {}
        for value in incoming:
            ident = value["id"]
            old = work_nodes.get(mapped[ident])
            norm = normalize_name(value.get("name") or "")
            choices = []
            for cid in touched_aliases.get(norm, []):
                cid = mapped.get(cid, cid)
                candidate = work_nodes.get(cid)
                if not candidate or not types_compatible(candidate.get("type"), value.get("type")): continue
                a, b = self._website(candidate), self._website(value)
                if a and b and a != b: continue
                choices.append((cid, candidate))
            if old:
                chosen = mapped[ident]
            elif choices:
                chosen, old = choices[0]
                if value.get("type") == "Company" and old.get("type") != "Company": chosen = ident
            else:
                chosen = ident
            canonical[ident] = chosen
            if chosen != ident and ident not in work_nodes:
                repoints[ident] = chosen
            if old and old.get("id") != chosen:
                repoints[old["id"]] = chosen
            merged = self._merge(old, value, chosen) if old else dict(value, id=chosen)
            if expand and ident == str(expand[0]):
                merged.setdefault("expanded", {})[rels_key(expand[1])] = now_iso()
                merged["truncated"] = bool(merged.get("truncated") or expand[2])
            if old and old.get("id") != chosen: old_ids.add(old["id"])
            merged["merged_ids"] = [x for x in merged.get("merged_ids", []) if x != chosen]
            for previous in merged.get("merged_ids", []):
                if previous != chosen: old_ids.add(previous)
            for prior in (ident, *(old.get("merged_ids", []) if old else [])):
                if prior != chosen: old_ids.add(prior)
            work_nodes[chosen] = merged
            node_sets[chosen] = merged
            for name in self._aliases(merged):
                alias_norm = normalize_name(name)
                if alias_norm:
                    touched_aliases.setdefault(alias_norm, [])
                    if chosen not in touched_aliases[alias_norm]: touched_aliases[alias_norm].append(chosen)
        saved_edges = []
        edge_sets = {}
        if repoints:
            old_ids.update(repoints)
            old_list = sorted(repoints)
            old_edge_ids = sorted(set().union(*(adj_by_id.get(i, set()) for i in old_list)))
            old_raw = self.kv.mget([self._k("edge", i) for i in old_edge_ids])
            for eid, value in zip(old_edge_ids, old_raw):
                edge = _json(value)
                if not edge:
                    continue
                edge["src"] = repoints.get(edge["src"], edge["src"])
                edge["dst"] = repoints.get(edge["dst"], edge["dst"])
                edge_sets[eid] = edge
                for endpoint in (edge["src"], edge["dst"]):
                    adj_adds.setdefault(endpoint, set()).add(eid)
        for edge in edge_values:
            edge["src"] = canonical.get(str(edge["src"]), mapped.get(str(edge["src"]), str(edge["src"])))
            edge["dst"] = canonical.get(str(edge["dst"]), mapped.get(str(edge["dst"]), str(edge["dst"])))
            edge["src"] = repoints.get(edge["src"], edge["src"])
            edge["dst"] = repoints.get(edge["dst"], edge["dst"])
            if edge["src"] == edge["dst"]: continue
            edge["sources"] = edge.get("sources") or []
            edge.setdefault("loaded_at", now_iso())
            if not edge.get("id"):
                digest = hashlib.sha1("|".join(str(edge.get(k, "")) for k in
                    ("src", "rel", "dst", "role")).encode()).hexdigest()[:16]
                edge["id"] = "e:" + digest
            old_edge = _json(raw.get(self._k("edge", str(edge["id"]))))
            if old_edge:
                old_edge.update({k: v for k, v in edge.items() if k != "sources" and _nonempty(v)})
                old_edge["sources"] = _sources(old_edge.get("sources"), edge["sources"])
                edge = old_edge
            edge_sets[edge["id"]] = edge
            saved_edges.append(edge["id"])
            for endpoint in (edge["src"], edge["dst"]):
                adj_adds.setdefault(endpoint, set()).add(edge["id"])
        sets = [(self._k("node", i), _dump(v), self.ttl_s) for i, v in node_sets.items()]
        sets += [(self._k("edge", i), _dump(v), self.ttl_s) for i, v in edge_sets.items()]
        sets += [(self._k("alias:id", i), v, self.ttl_s) for i, v in alias_id_sets.items()]
        for ident in old_ids:
            target = repoints.get(ident) or next((v for k, v in canonical.items() if k == ident), None)
            if target is None and node_sets:
                target = next(iter(node_sets))
            if target:
                sets.append((self._k("alias:id", ident), target, self.ttl_s))
                deletes.extend((self._k("node", ident), self._k("adj", ident)))
        for ident, target in canonical.items():
            if target != ident:
                sets.append((self._k("alias:id", ident), target, self.ttl_s))
        for norm, values in touched_aliases.items():
            values = [repoints.get(x, canonical.get(x, mapped.get(x, x))) for x in values]
            sets.append((self._k("alias", norm), _dump(list(dict.fromkeys(values))), self.ttl_s))
        adds = [(self._k("adj", i), sorted(v), self.ttl_s) for i, v in adj_adds.items()]
        self.kv.write_batch(sets, adds, deletes)
        self._cache_written(sets, adds, deletes)
        return canonical, saved_edges
    def put_node(self, node):
        return self._apply([node], [])[0][str(node["id"])]
    def put_edge(self, edge):
        saved = self._apply([], [edge])[1]
        return saved[0] if saved else None
    def view_seeds(self, user):
        ids = _json(self.kv.get(self._k("view", f"{user}:seeds"))) or []; mapped = self.canonical_ids(ids)
        return [mapped[str(i)] for i in ids]
    def view_nodes(self, user):
        ids = self.kv.smembers(self._k("view", f"{user}:nodes")); return set(self.canonical_ids(ids).values())
    def set_view(self, user, seeds, nodes):
        ids = list(dict.fromkeys([str(i) for i in seeds])); nodes = list(dict.fromkeys([str(i) for i in nodes]))
        mapped = self.canonical_ids(ids + nodes); key = self._k("view", f"{user}:nodes")
        sets = [(self._k("view", f"{user}:seeds"), _dump([mapped[i] for i in ids]), self.ttl_s)]
        adds = [(key, [mapped[i] for i in nodes], self.ttl_s)]
        self.kv.write_batch(sets, adds, [key])
        self._cache_written(sets, adds, [key])
    def add_to_view(self, user, node_ids):
        ids = list(dict.fromkeys(str(i) for i in node_ids)); mapped = self.canonical_ids(ids)
        key = self._k("view", f"{user}:nodes")
        self.kv.sadd(key, list(dict.fromkeys(mapped.values())), self.ttl_s)
        self._cache_written(adds=[(key, list(dict.fromkeys(mapped.values())), self.ttl_s)])
    def distance(self, sources, target, max_depth=3, within=None):
        ids = list(dict.fromkeys([str(x) for x in sources] + [str(target)])); mapped = self.canonical_ids(ids)
        target = mapped[str(target)]; start = {mapped[str(s)] for s in sources}
        if target in start: return 0
        if not self.get_nodes([target]): return None
        within_ids = set(self.canonical_ids(within).values()) if within is not None else None
        seen = set(start); frontier = start
        for depth in range(1, max_depth + 1):
            missing_adj = [n for n in sorted(frontier) if self._cache_get(("adj", n)) is None]
            groups = self.kv.smembers_many([self._k("adj", n) for n in missing_adj])
            fetched_groups = dict(zip(missing_adj, groups))
            for ident, group in zip(missing_adj, groups):
                self._cache_set(("adj", ident), sorted(group))
            groups = [set(self._cache_get(("adj", n)) if self._cache_get(("adj", n)) is not None
                          else fetched_groups.get(n, ())) for n in sorted(frontier)]
            edge_ids = sorted(set().union(*groups) if groups else set())
            decoded_map = {i: self._cache_get(("edge", i)) for i in edge_ids}
            missing_edges = [i for i in edge_ids if decoded_map[i] is None]
            vals = self.kv.mget([self._k("edge", i) for i in missing_edges])
            for ident, raw in zip(missing_edges, vals):
                decoded_map[ident] = _json(raw)
                if decoded_map[ident] is not None:
                    self._cache_set(("edge", ident), decoded_map[ident])
            nxt = set()
            decoded = [decoded_map[i] for i in edge_ids]
            for e in decoded:
                if not e: continue
                a, b = e["src"], e["dst"]
                if a in frontier: nxt.add(b)
                if b in frontier: nxt.add(a)
            nxt -= seen
            if within_ids is not None: nxt = {n for n in nxt if n == target or n in within_ids}
            if target in nxt: return depth
            seen |= nxt; frontier = nxt
            if not frontier: break
        return None
    def is_expanded(self, node_id, rels, max_age_s=None):
        return node_is_expanded(self.get_node(node_id), rels, self.ttl_s if max_age_s is None else max_age_s)
    def mark_expanded(self, node_id, rels, truncated=False):
        node = self.get_node(node_id)
        if not node: return
        node.setdefault("expanded", {})[rels_key(rels)] = now_iso()
        node["truncated"] = bool(node.get("truncated") or truncated)
        key = self._k("node", node["id"])
        self._put_json(key, node)
        self._cache_written([(key, _dump(node), self.ttl_s)])
    def put_expansion(self, node, edges, neighbors, *, rels, truncated=False):
        """Guarda los elementos recibidos y marca el conjunto de relaciones como expandido."""
        mapped, _ = self._apply([node, *neighbors], edges, (str(node["id"]), rels, truncated))
        return mapped[str(node["id"])]
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
        if connected: _STORE = GraphStore(kv, ttl_s=int(os.getenv("GRAPH_TTL_S", TTL_S)), cache_size=20000); _STORE.backend = "valkey"; return _STORE
    _STORE = GraphStore(MemoryKV()); _STORE.backend = "memory"; return _STORE
