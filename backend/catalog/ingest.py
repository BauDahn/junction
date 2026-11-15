"""Ingesta reanudable del catálogo de Slush 2026 hacia Valkey/memoria y el grafo compartido."""
import asyncio
import fnmatch
import hashlib
import inspect
import json
import logging
import math
import os
import re
import threading
import time
import uuid
from email.utils import parsedate_to_datetime
from datetime import date, datetime, timezone
from pathlib import Path
from statistics import quantiles

import httpx

from canonizador.cache import load_env
from canonizador.client import CalaClient
from core.config import settings
from core.llm import make_llm

logger = logging.getLogger(__name__)

SLUSH_EVENT_ID = "bc844d56-6ab4-452b-96bf-2661e86e592b"
TTL_S = 7 * 24 * 3600
LOCK_TTL_S = 600
LOCK_KEY = "cat:v1:lock"
STATUS_KEY = "cat:v1:status"
TODO_KEY = "cat:v1:todo"
ATTENDEES_KEY = "cat:v1:attendees"
FEAT_PREFIX = "cat:v1:feat:"
FAILED_PREFIX = "cat:v1:failed:"
GRAPH_PREFIX = "graph:v1:"


async def _sleep(seconds):
    await asyncio.sleep(seconds)


def _retry_after_seconds(exc):
    value = exc.response.headers.get("Retry-After")
    if not value:
        return None
    try:
        seconds = float(value)
        return seconds if seconds >= 0 else None
    except (TypeError, ValueError):
        try:
            return max(0.0, (parsedate_to_datetime(value) - datetime.now(timezone.utc)).total_seconds())
        except (TypeError, ValueError, OverflowError):
            return None

STAGE2_PROPERTIES = [
    "name", "description", "funding_stage", "total_funding",
    "total_funding_units", "employee_count_range", "website",
    "headquarters", "headquarters_address", "sede",
]
STAGE2_RELATIONSHIPS = {
    "incoming": {"INVESTED_IN": {"limit": 100}, "FOUNDED": {"limit": 100}},
    "outgoing": {"INVESTED_IN": {"limit": 100}, "PARTICIPATES_IN_FUNDING_ROUND": {"limit": 100}},
}
STAGE2_RELS = ("INVESTED_IN", "PARTICIPATES_IN_FUNDING_ROUND", "FOUNDED")
EXCLUDED_TYPES = frozenset({
    "PrivateCompanyFundingRound", "Product", "Award", "Country", "Group", "EducationalInstitution",
})

_UNIT_MULT = {
    "k": 1e3, "thousand": 1e3,
    "m": 1e6, "mm": 1e6, "million": 1e6,
    "bn": 1e9, "b": 1e9, "billion": 1e9,
}
_COUNTRY_HINTS = {
    "finland": "Finland", "suomi": "Finland", "helsinki": "Finland", "espoo": "Finland",
    "sweden": "Sweden", "sverige": "Sweden", "stockholm": "Sweden",
    "norway": "Norway", "oslo": "Norway",
    "denmark": "Denmark", "copenhagen": "Denmark",
    "iceland": "Iceland", "reykjavik": "Iceland",
    "germany": "Germany", "berlin": "Germany", "munich": "Germany",
    "austria": "Austria", "vienna": "Austria",
    "switzerland": "Switzerland", "zurich": "Switzerland", "geneva": "Switzerland",
    "spain": "Spain", "espana": "Spain", "españa": "Spain", "madrid": "Spain", "barcelona": "Spain", "valencia": "Spain",
    "portugal": "Portugal", "lisbon": "Portugal",
    "france": "France", "paris": "France",
    "uk": "United Kingdom", "united kingdom": "United Kingdom", "london": "United Kingdom",
    "ireland": "Ireland", "dublin": "Ireland",
    "netherlands": "Netherlands", "amsterdam": "Netherlands",
    "belgium": "Belgium", "brussels": "Belgium",
    "estonia": "Estonia", "tallinn": "Estonia",
    "latvia": "Latvia", "riga": "Latvia",
    "lithuania": "Lithuania", "vilnius": "Lithuania",
    "italy": "Italy", "milan": "Italy", "rome": "Italy",
    "poland": "Poland", "warsaw": "Poland",
    "usa": "United States", "us": "United States", "united states": "United States",
    "san francisco": "United States", "new york": "United States", "boston": "United States",
}

TAG_SCHEMA = {
    "type": "object",
    "properties": {
        "sectors": {"type": "array", "items": {"type": "string"}},
        "stages": {"type": "array", "items": {"type": "string"}},
        "customer_type": {"type": "string"},
        "country": {"type": "string"},
        "hq": {"type": "string"},
        "region": {"type": "string"},
    },
}
TAG_SYSTEM = (
    "Extract structured startup or investor tags strictly from the given description and HQ text. "
    "Use standard concise English sector names (e.g. Fintech, SaaS, AI, Climate Tech, Healthtech), "
    "stages (Pre-Seed, Seed, Series A, Series B, Series C, Growth), customer_type (B2B, B2C, B2B2C, Enterprise, SMB), "
    "country, hq, and region (Nordics, Iberia, DACH, Baltics, Benelux, UK & Ireland, Europe). "
    "Return empty strings or empty arrays when unknown; do not invent facts."
)


class CatalogLockError(RuntimeError):
    """Error lanzado cuando otro proceso ya mantiene el lock del catálogo."""


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


def _json_load(raw):
    if raw is None:
        return None
    if isinstance(raw, (dict, list)):
        return raw
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        return None


def _json_dump(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


class MemoryCatalogKV:
    """Almacén clave-valor en memoria con TTL y bloqueo atómico SET NX."""

    def __init__(self):
        self.data = {}
        self.expiry = {}
        self._lock = threading.Lock()

    def _live_unlocked(self, key):
        exp = self.expiry.get(key)
        if exp is not None and exp <= time.time():
            self.data.pop(key, None)
            self.expiry.pop(key, None)
            return None
        return self.data.get(key)

    def get(self, key):
        with self._lock:
            return self._live_unlocked(key)

    def mget(self, keys):
        with self._lock:
            return [self._live_unlocked(k) for k in keys]

    def set(self, key, value, ttl=TTL_S):
        with self._lock:
            self.data[key] = value
            self.expiry[key] = time.time() + ttl if ttl else float("inf")
        return True

    def set_nx(self, key, value, ttl=LOCK_TTL_S):
        with self._lock:
            if self._live_unlocked(key) is not None:
                return False
            self.data[key] = value
            self.expiry[key] = time.time() + ttl if ttl else float("inf")
            return True

    def delete(self, key):
        with self._lock:
            self.data.pop(key, None)
            self.expiry.pop(key, None)

    def delete_if_equals(self, key, expected):
        with self._lock:
            if self._live_unlocked(key) == expected:
                self.data.pop(key, None)
                self.expiry.pop(key, None)
                return True
            return False

    def refresh_lock_if_equals(self, key, expected, ttl=LOCK_TTL_S):
        with self._lock:
            if self._live_unlocked(key) != expected:
                return False
            self.expiry[key] = time.time() + ttl if ttl else float("inf")
            return True

    def sadd(self, key, members, ttl=TTL_S):
        with self._lock:
            current = self._live_unlocked(key)
            updated = set(current) if isinstance(current, set) else set()
            updated.update(members)
            self.data[key] = updated
            self.expiry[key] = time.time() + ttl if ttl else float("inf")

    def smembers(self, key):
        with self._lock:
            val = self._live_unlocked(key)
            return set(val) if isinstance(val, set) else set()

    def smembers_many(self, keys):
        return [self.smembers(k) for k in keys]

    def scan_prefix(self, prefix):
        pattern = f"{prefix}*"
        with self._lock:
            return [
                k for k in list(self.data)
                if self._live_unlocked(k) is not None and fnmatch.fnmatch(k, pattern)
            ]

    def keys(self, pattern):
        with self._lock:
            return [
                k for k in list(self.data)
                if self._live_unlocked(k) is not None and fnmatch.fnmatch(k, pattern)
            ]

    def ping(self):
        return True


class RedisCatalogKV:
    """Adaptador de catálogo sobre Valkey/Redis (o un cliente compatible en tests)."""

    _RELEASE_LUA = "if redis.call('get', KEYS[1]) == ARGV[1] then return redis.call('del', KEYS[1]) else return 0 end"
    _REFRESH_LUA = "if redis.call('get', KEYS[1]) == ARGV[1] then return redis.call('expire', KEYS[1], tonumber(ARGV[2])) else return 0 end"

    def __init__(self, url=None, client=None, timeout_s=3.0, connect_timeout_s=8.0):
        self.url = url
        self.client = client
        self.timeout_s = timeout_s
        self.connect_timeout_s = connect_timeout_s

    def _client(self):
        if self.client is None:
            import redis
            self.client = redis.Redis.from_url(
                self.url,
                socket_connect_timeout=self.connect_timeout_s,
                socket_timeout=self.timeout_s,
                decode_responses=True,
            )
        return self.client

    def get(self, key):
        return self._client().get(key)

    def mget(self, keys):
        return self._client().mget(list(keys)) if keys else []

    def set(self, key, value, ttl=TTL_S):
        return bool(self._client().set(key, value, ex=ttl if ttl else None))

    def set_nx(self, key, value, ttl=LOCK_TTL_S):
        client = self._client()
        sig = inspect.signature(client.set)
        if "nx" in sig.parameters or any(p.kind == p.VAR_KEYWORD for p in sig.parameters.values()):
            return bool(client.set(key, value, ex=ttl if ttl else None, nx=True))
        if client.get(key) is not None:
            return False
        client.set(key, value, ex=ttl if ttl else None)
        return True

    def delete(self, key):
        self._client().delete(key)

    def delete_if_equals(self, key, expected):
        client = self._client()
        if hasattr(client, "eval"):
            try:
                return bool(client.eval(self._RELEASE_LUA, 1, key, expected))
            except Exception:
                pass
        if client.get(key) == expected:
            client.delete(key)
            return True
        return False

    def refresh_lock_if_equals(self, key, expected, ttl=LOCK_TTL_S):
        client = self._client()
        ttl_s = max(1, int(math.ceil(ttl if ttl is not None else LOCK_TTL_S)))
        if hasattr(client, "eval"):
            try:
                return bool(client.eval(self._REFRESH_LUA, 1, key, expected, ttl_s))
            except Exception:
                pass
        if client.get(key) != expected:
            return False
        if hasattr(client, "expire"):
            res = client.expire(key, ttl_s)
            return True if res is None else bool(res)
        client.set(key, expected, ex=ttl_s)
        return True

    def sadd(self, key, members, ttl=TTL_S):
        client = self._client()
        if members:
            client.sadd(key, *members)
        if ttl:
            client.expire(key, ttl)

    def smembers(self, key):
        return set(self._client().smembers(key))

    def smembers_many(self, keys):
        if not keys:
            return []
        client = self._client()
        pipe = client.pipeline()
        for key in keys:
            pipe.smembers(key)
        return [set(s) for s in pipe.execute()]

    def scan_prefix(self, prefix):
        return list(self._client().scan_iter(match=f"{prefix}*"))

    def keys(self, pattern):
        return list(self._client().scan_iter(match=pattern))

    def ping(self):
        return bool(self._client().ping())


class _WrappedStoreKV:
    """Envuelve MemoryKV o ValkeyKV de backend/graph/store.py añadiendo set_nx y scan_prefix."""

    def __init__(self, inner):
        self.inner = inner
        self._lock = threading.Lock()

    def get(self, key):
        return self.inner.get(key)

    def mget(self, keys):
        return self.inner.mget(list(keys)) if keys else []

    def set(self, key, value, ttl=TTL_S):
        return self.inner.set(key, value, ttl)

    def set_nx(self, key, value, ttl=LOCK_TTL_S):
        if hasattr(self.inner, "_client"):
            return RedisCatalogKV(client=self.inner._client()).set_nx(key, value, ttl)
        with self._lock:
            if self.inner.get(key) is not None:
                return False
            self.inner.set(key, value, ttl)
            return True

    def delete(self, key):
        self.inner.delete(key)

    def delete_if_equals(self, key, expected):
        if hasattr(self.inner, "_client"):
            return RedisCatalogKV(client=self.inner._client()).delete_if_equals(key, expected)
        with self._lock:
            if self.inner.get(key) == expected:
                self.inner.delete(key)
                return True
            return False

    def refresh_lock_if_equals(self, key, expected, ttl=LOCK_TTL_S):
        if hasattr(self.inner, "_client"):
            return RedisCatalogKV(client=self.inner._client()).refresh_lock_if_equals(key, expected, ttl)
        with self._lock:
            if self.inner.get(key) != expected:
                return False
            self.inner.set(key, expected, ttl)
            return True

    def sadd(self, key, members, ttl=TTL_S):
        self.inner.sadd(key, members, ttl)

    def smembers(self, key):
        return self.inner.smembers(key)

    def smembers_many(self, keys):
        return self.inner.smembers_many(keys)

    def scan_prefix(self, prefix):
        return list(self.inner.keys(f"{prefix}*"))

    def keys(self, pattern):
        return list(self.inner.keys(pattern))

    def ping(self):
        return self.inner.ping()


def _wrap_kv(kv):
    if hasattr(kv, "set_nx") and hasattr(kv, "scan_prefix"):
        return kv
    return _WrappedStoreKV(kv)


def _env_float(name, default):
    try:
        return max(0.1, float(os.getenv(name, str(default))))
    except (TypeError, ValueError):
        return default


def make_kv(store=None, url=None, client=None):
    """Devuelve un KV compatible para el catálogo (Valkey si está disponible, o memoria)."""
    if client is not None:
        return RedisCatalogKV(client=client)
    if store is not None and hasattr(store, "kv"):
        return _wrap_kv(store.kv)
    if url is None:
        load_env()
        url = (os.getenv("VALKEY_URL") or "").strip()
    if url:
        kv = RedisCatalogKV(
            url=url,
            timeout_s=_env_float("VALKEY_TIMEOUT", 3.0),
            connect_timeout_s=_env_float("VALKEY_CONNECT_TIMEOUT", 8.0),
        )
        try:
            if kv.ping():
                return kv
        except Exception:
            logger.warning("Valkey no disponible; usando MemoryCatalogKV")
    return MemoryCatalogKV()


class _FallbackGraphStore:
    """Respaldo compatible con GraphStore (#64) mientras backend/graph aún no está en main."""

    def __init__(self, kv, ttl_s=TTL_S, prefix=GRAPH_PREFIX):
        self.kv = _wrap_kv(kv)
        self.ttl_s = ttl_s
        self.prefix = prefix

    def _k(self, kind, ident):
        return f"{self.prefix}{kind}:{ident}"

    def get_node(self, node_id):
        return _json_load(self.kv.get(self._k("node", str(node_id))))

    def get_nodes(self, ids):
        keys = [self._k("node", str(i)) for i in ids]
        vals = self.kv.mget(keys)
        out = {}
        for ident, raw in zip(ids, vals):
            node = _json_load(raw)
            if node:
                out[str(ident)] = node
        return out

    def get_edge(self, edge_id):
        return _json_load(self.kv.get(self._k("edge", str(edge_id))))

    def edges_of(self, node_id, require_sources=False):
        ids = sorted(self.kv.smembers(self._k("adj", str(node_id))))
        vals = self.kv.mget([self._k("edge", i) for i in ids])
        edges = [_json_load(v) for v in vals]
        return sorted(
            [e for e in edges if e and (not require_sources or e.get("sources"))],
            key=lambda e: str(e.get("id", "")),
        )

    def neighbors(self, node_id_or_ids, rels=None, require_sources=False):
        def one(nid):
            cur = str(nid)
            found = [e for e in self.edges_of(cur, require_sources) if rels is None or e.get("rel") in rels]
            other_ids = [str(e["dst"] if str(e["src"]) == cur else e["src"]) for e in found]
            nodes = self.get_nodes(other_ids)
            return [(e, nodes[oid]) for e, oid in zip(found, other_ids) if oid in nodes]

        if isinstance(node_id_or_ids, (list, tuple, set)):
            return {str(i): one(i) for i in node_id_or_ids}
        return one(node_id_or_ids)

    def put_node(self, node):
        nid = str(node["id"])
        existing = self.get_node(nid) or {}
        merged = {**existing, **node, "id": nid}
        props = dict(existing.get("props") or {})
        props.update({k: v for k, v in (node.get("props") or {}).items() if v not in (None, "", [], {})})
        merged["props"] = props
        exp = dict(existing.get("expanded") or {})
        exp.update(node.get("expanded") or {})
        merged["expanded"] = exp
        merged["truncated"] = bool(existing.get("truncated") or node.get("truncated"))
        self.kv.set(self._k("node", nid), _json_dump(merged), self.ttl_s)
        return nid

    def put_edge(self, edge):
        eid = str(edge["id"])
        src, dst = str(edge["src"]), str(edge["dst"])
        if src == dst:
            return None
        stored = dict(edge)
        stored["id"], stored["src"], stored["dst"] = eid, src, dst
        self.kv.set(self._k("edge", eid), _json_dump(stored), self.ttl_s)
        self.kv.sadd(self._k("adj", src), [eid], self.ttl_s)
        self.kv.sadd(self._k("adj", dst), [eid], self.ttl_s)
        return eid

    def mark_expanded(self, node_id, key, truncated=False):
        node = self.get_node(node_id)
        if not node:
            return
        node.setdefault("expanded", {})[key] = _now_iso()
        node["truncated"] = bool(node.get("truncated") or truncated)
        self.kv.set(self._k("node", node["id"]), _json_dump(node), self.ttl_s)

    def put_expansion(self, node, edges, neighbors=(), *, rels=(), truncated=False):
        cid = self.put_node(node)
        for neighbor in neighbors:
            self.put_node(neighbor)
        for edge in edges:
            self.put_edge(edge)
        rels_key = ",".join(sorted(set(rels or ())))
        if rels_key:
            self.mark_expanded(cid, rels_key, truncated=truncated)
        return cid


def _resolve_kv_and_store(kv=None, store=None):
    if store is None and kv is None:
        try:
            from graph.store import get_store
            store = get_store()
        except ImportError:
            store = None
    resolved_kv = _wrap_kv(kv) if kv is not None else make_kv(store=store)
    resolved_store = store if store is not None else _FallbackGraphStore(resolved_kv)
    return resolved_kv, resolved_store


def make_graph_store(kv):
    """Usa backend.graph.store.get_store() si existe; si no, el respaldo local."""
    try:
        from graph.store import get_store
        return get_store()
    except ImportError:
        return _FallbackGraphStore(kv)


def _save_expansion(store, center_node, edges, neighbor_nodes, *, rels=STAGE2_RELS, truncated=False):
    """Guarda expansión tolerando la firma de PR #81, el WIP previo y MemoryGraph/put_node."""
    if store is None:
        return center_node["id"]
    rels_key = ",".join(sorted(set(rels)))
    if hasattr(store, "put_expansion"):
        sig = inspect.signature(store.put_expansion)
        params = list(sig.parameters.values())
        names = [p.name for p in params]
        rels_kw_only = any(p.name == "rels" and p.kind == p.KEYWORD_ONLY for p in params)
        if rels_kw_only or (names and names[0] == "node"):
            return store.put_expansion(center_node, edges, neighbor_nodes, rels=rels, truncated=truncated)
        if len(names) >= 2 and names[1] == "rels":
            return store.put_expansion(
                center_node["id"], rels, nodes=[center_node, *neighbor_nodes], edges=edges, truncated=truncated,
            )
        return store.put_expansion(
            center_node["id"], [center_node, *neighbor_nodes], edges, rels_key, truncated,
        )
    if hasattr(store, "put_node") and hasattr(store, "put_edge"):
        cid = store.put_node(center_node)
        for neighbor in neighbor_nodes:
            store.put_node(neighbor)
        for edge in edges:
            store.put_edge(edge)
        if hasattr(store, "mark_expanded"):
            store.mark_expanded(cid, rels_key, truncated=truncated)
        return cid
    if hasattr(store, "add_node") and hasattr(store, "add_edge"):
        store.add_node(center_node)
        for neighbor in neighbor_nodes:
            store.add_node(neighbor)
        for edge in edges:
            store.add_edge(edge)
        return center_node["id"]
    return center_node["id"]


def _str(value):
    return str(value).strip() if isinstance(value, str) else (str(value).strip() if isinstance(value, (int, float)) and not isinstance(value, bool) else "")


def _prop_val(props, *keys):
    if not isinstance(props, dict):
        return None
    for key in keys:
        entry = props.get(key)
        val = entry.get("value") if isinstance(entry, dict) and "value" in entry else entry
        if val not in (None, ""):
            return val
    return None


def _valid_sources(raw):
    if not isinstance(raw, list):
        return []
    return [item for item in raw if isinstance(item, dict) and (item.get("name") or item.get("url") or item.get("document"))]


def _dedupe_sources(sources, limit=20):
    out, seen = [], set()
    for src in sources:
        if not isinstance(src, dict):
            continue
        key = src.get("url") or src.get("name") or _json_dump(src)
        if key and key not in seen:
            seen.add(key)
            out.append(src)
            if len(out) >= limit:
                break
    return out


def _extract_prop_sources(props):
    """Extrae fuentes únicamente desde dentro de `properties` (nunca del elemento raíz)."""
    if not isinstance(props, dict):
        return []
    found = []
    if isinstance(props.get("sources"), list):
        found.extend(_valid_sources(props["sources"]))
    for key, entry in props.items():
        if key == "sources":
            continue
        if isinstance(entry, dict) and isinstance(entry.get("sources"), list):
            found.extend(_valid_sources(entry["sources"]))
    return _dedupe_sources(found)


def _prop_sources_for(props, *keys):
    if not isinstance(props, dict):
        return []
    found = []
    for key in keys:
        entry = props.get(key)
        if isinstance(entry, dict):
            found.extend(_valid_sources(entry.get("sources")))
    return _dedupe_sources(found) or _valid_sources(props.get("sources"))


def _parse_numeric_amount(value):
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        num = float(value)
        return num if math.isfinite(num) and num > 0 else None
    text = str(value).strip()
    if not text:
        return None
    cleaned = re.sub(r",(?=\d{3}(?!\d))", "", text)
    cleaned = re.sub(r"(\d),(\d{1,2})(?!\d)", r"\1.\2", cleaned)
    matches = re.findall(r"(?<![A-Za-z])(\d+(?:\.\d+)?)\s*(bn|billion|mm|million|thousand|k|m|b)?\b", cleaned, re.I)
    if not matches:
        return None
    vals, trailing = [], None
    for raw_num, unit in reversed(matches):
        unit_key = unit.lower() if unit else trailing
        if unit:
            trailing = unit_key
        val = float(raw_num) * _UNIT_MULT.get(unit_key, 1.0)
        if math.isfinite(val) and val > 0:
            vals.append(val)
    return sum(vals) / len(vals) if vals else None


def _extract_year(value):
    if value is None:
        return None
    match = re.search(r"(?:19|20)\d{2}", str(value))
    return int(match.group()) if match else None


def _country_from_text(text):
    if not isinstance(text, str) or not text.strip():
        return None
    try:
        from api.regions import country_of
        found = country_of(text)
        if found:
            return found
    except ImportError:
        pass
    whole = text.strip().casefold()
    if whole in _COUNTRY_HINTS:
        return _COUNTRY_HINTS[whole]
    for part in reversed([p.strip().casefold() for p in text.split(",")]):
        if part in _COUNTRY_HINTS:
            return _COUNTRY_HINTS[part]
    return None


def _parse_hq_country(raw_hq):
    hq = _str(raw_hq) or None
    if not hq:
        return None, None
    return hq, _country_from_text(hq)


def _edge_id(src, rel, dst, role):
    digest = hashlib.sha1("|".join(str(x or "") for x in (src, rel, dst, role)).encode()).hexdigest()[:16]
    return f"e:{digest}"


def _infer_round_type(name):
    text = str(name or "")
    for pat in ("Pre-Seed", "Seed", "Series A", "Series B", "Series C", "Series D", "Series E", "Growth"):
        if pat.casefold() in text.casefold():
            return pat
    return ""


def _build_node_props(props, prop_sources, hq, country):
    node_props = {}
    if isinstance(props, dict):
        for key in STAGE2_PROPERTIES:
            if key not in props:
                continue
            entry = props[key]
            if isinstance(entry, dict) and "value" in entry:
                if entry.get("value") not in (None, ""):
                    node_props[key] = {"value": entry["value"], "sources": _valid_sources(entry.get("sources")) or prop_sources}
            elif entry not in (None, ""):
                node_props[key] = {"value": entry, "sources": prop_sources}
    hq_sources = _prop_sources_for(props, "headquarters", "headquarters_address", "sede") or prop_sources
    if hq:
        node_props["hq"] = {"id": None, "name": hq, "sources": hq_sources}
    if country:
        node_props["country"] = {"id": None, "name": country, "sources": hq_sources}
    if prop_sources:
        node_props["sources"] = prop_sources
    return node_props


def _extract_attendee_artifacts(attendee, data, *, today=None):
    """Construye nodo central, aristas, vecinos y características base desde Cala."""
    today = today or date.today()
    loaded_at = _now_iso()
    eid = str(attendee["id"])
    props = data.get("properties") or {}
    prop_sources = _extract_prop_sources(props)
    name = _str(_prop_val(props, "name") or data.get("name") or attendee.get("name") or eid)
    entity_type = _str(data.get("entity_type") or attendee.get("type") or "Company") or "Company"
    description = _str(_prop_val(props, "description"))
    funding_stage = _str(_prop_val(props, "funding_stage"))
    total_funding = _prop_val(props, "total_funding")
    hq_raw = _str(_prop_val(props, "headquarters", "headquarters_address", "sede"))
    hq, country = _parse_hq_country(hq_raw)

    relationships = data.get("relationships") or {}
    truncated = any(
        isinstance(items, list) and len(items) >= 100
        for by_rel in relationships.values() if isinstance(by_rel, dict)
        for items in by_rel.values()
    )

    kinds = []
    neighbor_nodes = {}
    edges = []
    rel_sources = []
    investor_rounds = []
    startup_rounds = []
    investor_amounts = []
    rounds_24m = 0
    led_24m = 0
    has_is_lead = False
    has_dated_inv = False
    cutoff_year = today.year - 2

    for direction in ("incoming", "outgoing"):
        by_rel = relationships.get(direction) or {}
        if not isinstance(by_rel, dict):
            continue
        for rel, items in by_rel.items():
            for item in items or []:
                if not isinstance(item, dict) or not item.get("id"):
                    continue
                nid = str(item["id"])
                ntype = _str(item.get("entity_type")) or ("Person" if rel == "FOUNDED" else "Company")
                nname = _str(item.get("name")) or nid
                ip = item.get("properties") or {}
                # Regla de Cala: leer sources solo de item["properties"]["sources"], nunca de item["sources"].
                esources = _valid_sources(ip.get("sources"))
                role = _prop_val(ip, "role")
                is_lead = _prop_val(ip, "is_lead")
                valid_since = _str(_prop_val(ip, "valid_since")) or None
                valid_until = _str(_prop_val(ip, "valid_until")) or None
                event_date = _str(_prop_val(ip, "event_date")) or valid_since
                rel_sources.extend(esources)

                if direction == "outgoing" and rel == "INVESTED_IN":
                    if "investor" not in kinds:
                        kinds.append("investor")
                    if esources:
                        amt = _parse_numeric_amount(_prop_val(ip, "funding_amount", "transaction_value", "amount"))
                        yr = _extract_year(event_date)
                        rtype = _str(_prop_val(ip, "round_type", "round_label"))
                        sec = _str(_prop_val(ip, "sector"))
                        loc = _str(_prop_val(ip, "location"))
                        if amt is not None:
                            investor_amounts.append(amt)
                        if yr is not None:
                            has_dated_inv = True
                            if yr >= cutoff_year:
                                rounds_24m += 1
                                if is_lead:
                                    led_24m += 1
                        if is_lead is not None:
                            has_is_lead = True
                        r_entry = {"company": nname, "sources": esources}
                        if rtype:
                            r_entry["round_type"] = rtype
                        if amt is not None:
                            r_entry["funding_amount"] = amt
                        if yr is not None:
                            r_entry["year"] = yr
                        if is_lead is not None:
                            r_entry["is_lead"] = bool(is_lead)
                        if sec:
                            r_entry["sector"] = sec
                        if loc:
                            r_entry["location"] = loc
                        investor_rounds.append(r_entry)

                elif direction == "outgoing" and rel == "PARTICIPATES_IN_FUNDING_ROUND":
                    if str(role or "").upper() == "ISSUER":
                        if "startup" not in kinds:
                            kinds.append("startup")
                        if esources:
                            amt = _parse_numeric_amount(_prop_val(ip, "funding_amount", "transaction_value", "amount"))
                            yr = _extract_year(event_date)
                            rtype = _str(_prop_val(ip, "round_type", "round_label")) or _infer_round_type(nname)
                            if rtype or amt is not None or yr is not None:
                                r_entry = {"leads": [], "investors": [], "sources": esources}
                                if rtype:
                                    r_entry["round_type"] = rtype
                                if amt is not None:
                                    r_entry["funding_amount"] = amt
                                if yr is not None:
                                    r_entry["year"] = yr
                                startup_rounds.append(r_entry)

                if ntype in EXCLUDED_TYPES:
                    continue
                if nid != eid:
                    neighbor_nodes.setdefault(nid, {
                        "id": nid, "type": ntype, "name": nname,
                        "aliases": [], "merged_ids": [], "props": {},
                        "loaded_at": loaded_at, "expanded": {}, "truncated": False,
                    })
                src, dst = (eid, nid) if direction == "outgoing" else (nid, eid)
                if src == dst:
                    continue
                edge_id = _str(_prop_val(ip, "id")) or _edge_id(src, rel, dst, role)
                edge = {
                    "id": edge_id, "src": src, "dst": dst, "rel": rel,
                    "sources": esources, "loaded_at": loaded_at,
                }
                if role is not None:
                    edge["role"] = role
                if is_lead is not None:
                    edge["is_lead"] = bool(is_lead)
                if valid_since:
                    edge["valid_since"] = valid_since
                if valid_until:
                    edge["valid_until"] = valid_until
                if event_date:
                    edge["event_date"] = event_date
                edges.append(edge)

    if len(investor_amounts) > 1:
        q = quantiles(investor_amounts, n=4, method="inclusive")
        amount = {"min": q[0], "max": q[2]}
    elif len(investor_amounts) == 1:
        amount = {"min": investor_amounts[0], "max": investor_amounts[0]}
    else:
        parsed_total = _parse_numeric_amount(total_funding) if prop_sources else None
        amount = {"min": parsed_total, "max": parsed_total}

    feature_sources = _dedupe_sources([*prop_sources, *rel_sources])
    rounds = investor_rounds if investor_rounds else startup_rounds
    stages = [funding_stage] if funding_stage and prop_sources else []

    center_node = {
        "id": eid, "type": entity_type, "name": name,
        "aliases": [], "merged_ids": [],
        "props": _build_node_props(props, prop_sources, hq, country),
        "loaded_at": loaded_at, "expanded": {}, "truncated": truncated,
    }
    features = {
        "id": eid,
        "name": name,
        "kinds": kinds,
        "description": description,
        "sectors": [],
        "stages": stages,
        "ai_tagged": False,
        "country": country,
        "hq": hq,
        "amount": amount,
        "activity": {
            "rounds_24m": rounds_24m if has_dated_inv else None,
            "led_24m": led_24m if (has_dated_inv and has_is_lead) else None,
        },
        "rounds": rounds,
        "sources": feature_sources,
        "loaded_at": loaded_at,
    }
    return center_node, edges, list(neighbor_nodes.values()), truncated, features


def _clean_tags(values):
    out, seen = [], set()
    for val in values or []:
        text = _str(val)
        if text and text.casefold() not in seen:
            seen.add(text.casefold())
            out.append(text)
    return out


async def _tag_features_with_llm(features, llm, semaphore):
    """Etiqueta sectores/etapas/región desde la descripción de Cala usando Gemini en paralelo."""
    description = features.get("description") or ""
    if not description or llm is None:
        return features
    prompt = f"Name: {features['name']}\nHQ: {features.get('hq') or ''}\nDescription:\n{description}"
    try:
        async with semaphore:
            tagged = await llm.complete_json(TAG_SYSTEM, prompt, TAG_SCHEMA)
    except Exception as exc:
        logger.warning("Fallo etiquetado LLM para %s: %s", features["id"], exc)
        return features
    if not isinstance(tagged, dict):
        return features
    sectors = _clean_tags(tagged.get("sectors"))
    stages = _clean_tags([*(features.get("stages") or []), *(tagged.get("stages") or [])])
    customer_type = _str(tagged.get("customer_type"))
    country = features.get("country") or _str(tagged.get("country")) or _country_from_text(_str(tagged.get("hq"))) or None
    hq = features.get("hq") or _str(tagged.get("hq")) or _str(tagged.get("region")) or None
    region = _str(tagged.get("region")) or None
    updated = dict(features)
    updated["sectors"] = sectors
    updated["stages"] = stages
    if customer_type:
        updated["customer_type"] = customer_type
    if country:
        updated["country"] = country
    if hq:
        updated["hq"] = hq
    if region:
        updated["region"] = region
    if sectors or stages or customer_type or tagged.get("country") or tagged.get("hq") or tagged.get("region"):
        updated["ai_tagged"] = True
    return updated


def _resolve_llm(llm):
    if llm is not None:
        return llm
    if not (settings.gemini_api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")):
        return None
    try:
        return make_llm(tier="fast")[0]
    except Exception as exc:
        logger.warning("No se pudo inicializar Gemini fast tier: %s", exc)
        return None


def _refresh_lock(kv, token, lock_ttl=LOCK_TTL_S):
    if not token:
        return True
    if hasattr(kv, "refresh_lock_if_equals"):
        ok = bool(kv.refresh_lock_if_equals(LOCK_KEY, token, ttl=lock_ttl))
    elif kv.get(LOCK_KEY) == token:
        kv.set(LOCK_KEY, token, lock_ttl)
        ok = True
    else:
        ok = False
    if not ok:
        raise CatalogLockError("Catalog ingest lock lost (cat:v1:lock expired or replaced).")
    return True


def _save_state(kv, status, todo, attendees=None, *, lock_token=None, lock_ttl=LOCK_TTL_S):
    _refresh_lock(kv, lock_token, lock_ttl=lock_ttl)
    status["updated_at"] = _now_iso()
    kv.set(STATUS_KEY, _json_dump(status), TTL_S)
    kv.set(TODO_KEY, _json_dump(todo), TTL_S)
    if attendees is not None:
        kv.set(ATTENDEES_KEY, _json_dump(attendees), TTL_S)


async def _fetch_stage1(cala, kv, limit, page_size=100, *, lock_token=None, lock_ttl=LOCK_TTL_S):
    status = _json_load(kv.get(STATUS_KEY)) or {}
    attendees = _json_load(kv.get(ATTENDEES_KEY)) or {}
    todo = _json_load(kv.get(TODO_KEY))
    if todo is None:
        todo = []

    if status.get("stage1_full"):
        return status, todo, attendees
    if status.get("stage1_done") and limit is not None and len(attendees) >= limit:
        return status, todo, attendees

    offset = int(status.get("stage1_offset") or 0)
    status.setdefault("done", 0)
    status.setdefault("investors", 0)
    status.setdefault("startups", 0)
    status.setdefault("ai_tagged", 0)
    status.setdefault("errors", 0)
    status["stage"] = "stage1"
    _save_state(kv, status, todo, attendees, lock_token=lock_token, lock_ttl=lock_ttl)

    while True:
        data = await cala.retrieve(
            SLUSH_EVENT_ID,
            properties=["name"],
            relationships={"incoming": {"PARTICIPATES_IN_EVENT": {"limit": page_size, "offset": offset}}},
        )
        items = ((data.get("relationships") or {}).get("incoming") or {}).get("PARTICIPATES_IN_EVENT") or []
        if not items:
            status["stage1_done"] = True
            status["stage1_full"] = True
            break
        for item in items:
            if not isinstance(item, dict) or not item.get("id"):
                continue
            eid = str(item["id"])
            if eid not in attendees:
                attendees[eid] = {
                    "id": eid,
                    "name": _str(item.get("name")) or eid,
                    "type": _str(item.get("entity_type")) or "Company",
                }
                todo.append(eid)
        offset += len(items)
        status["stage1_offset"] = offset
        status["total"] = len(attendees)
        _save_state(kv, status, todo, attendees, lock_token=lock_token, lock_ttl=lock_ttl)
        if len(items) < page_size:
            status["stage1_done"] = True
            status["stage1_full"] = True
            break
        if limit is not None and len(attendees) >= limit:
            status["stage1_done"] = True
            break

    status["total"] = len(attendees)
    _save_state(kv, status, todo, attendees, lock_token=lock_token, lock_ttl=lock_ttl)
    return status, todo, attendees


def _feat_flags(feat):
    kinds = feat.get("kinds") or []
    return (
        1 if "investor" in kinds else 0,
        1 if "startup" in kinds else 0,
        1 if feat.get("ai_tagged") else 0,
    )


def _seed_stats(kv):
    """Lee una única vez las características guardadas para actualizar contadores en O(1)."""
    keys = kv.scan_prefix(FEAT_PREFIX)
    vals = kv.mget(keys) if keys else []
    tracked = {}
    done = investors = startups = ai_tagged = 0
    for key, raw in zip(keys, vals):
        feat = _json_load(raw)
        if not isinstance(feat, dict):
            continue
        eid = str(feat.get("id") or key[len(FEAT_PREFIX):])
        flags = _feat_flags(feat)
        tracked[eid] = flags
        done += 1
        investors += flags[0]
        startups += flags[1]
        ai_tagged += flags[2]
    return {"done": done, "investors": investors, "startups": startups, "ai_tagged": ai_tagged}, tracked


def _count_stats(kv):
    counts, _ = _seed_stats(kv)
    return counts


async def run_catalog(
    *,
    limit=None,
    cala=None,
    llm=None,
    kv=None,
    store=None,
    cala_concurrency=2,
    llm_concurrency=4,
    page_size=100,
    today=None,
    lock_ttl=None,
):
    """Ejecuta las etapas 1–3 de forma reanudable y protegida con lock SET NX y renovación de TTL."""
    load_env()
    kv, store = _resolve_kv_and_store(kv=kv, store=store)
    effective_lock_ttl = LOCK_TTL_S if lock_ttl is None else lock_ttl
    token = uuid.uuid4().hex
    if not kv.set_nx(LOCK_KEY, token, ttl=effective_lock_ttl):
        raise CatalogLockError("Catalog ingest already running (cat:v1:lock held).")

    owned_http = None
    if cala is None:
        owned_http = httpx.AsyncClient(timeout=120)
        cala = CalaClient(settings.cala_api_key, settings.cache_dir, client=owned_http, entities_interval=0.7)
    resolved_llm = _resolve_llm(llm)

    stop_heartbeat = asyncio.Event()
    lock_lost_error = [None]
    tag_tasks = []

    async def _lock_heartbeat():
        interval = max(0.05, min(60.0, float(effective_lock_ttl) / 3.0))
        while not stop_heartbeat.is_set():
            try:
                await asyncio.wait_for(stop_heartbeat.wait(), timeout=interval)
                break
            except asyncio.TimeoutError:
                try:
                    _refresh_lock(kv, token, lock_ttl=effective_lock_ttl)
                except CatalogLockError as exc:
                    lock_lost_error[0] = exc
                    stop_heartbeat.set()
                    break

    heartbeat_task = asyncio.create_task(_lock_heartbeat())

    try:
        status, todo, attendees = await _fetch_stage1(
            cala, kv, limit=limit, page_size=page_size, lock_token=token, lock_ttl=effective_lock_ttl,
        )
        status.pop("stopped", None)
        existing_done = int(status.get("done") or 0)
        if limit is not None:
            remaining_cap = max(0, int(limit) - existing_done)
            work_ids = todo[:remaining_cap]
        else:
            work_ids = list(todo)

        if not work_ids:
            counts = _count_stats(kv)
            if lock_lost_error[0] is not None:
                raise lock_lost_error[0]
            status.update(counts)
            status["total"] = len(attendees) if attendees else max(counts["done"], int(status.get("total") or 0))
            status["stage"] = "done" if not todo else "paused"
            _save_state(kv, status, todo, lock_token=token, lock_ttl=effective_lock_ttl)
            return status

        counts, tracked = _seed_stats(kv)
        status["stage"] = "running"
        _save_state(kv, status, todo, lock_token=token, lock_ttl=effective_lock_ttl)

        todo_set = set(todo)
        state_lock = asyncio.Lock()
        payment_breaker = {"consecutive": 0, "tripped": False}
        payment_trip = max(1, int(os.getenv("CATALOG_402_TRIP", "5")))
        cala_sem = asyncio.Semaphore(max(1, int(cala_concurrency)))
        llm_sem = asyncio.Semaphore(max(1, int(llm_concurrency)))

        def _apply_feature_counts(eid, feat):
            flags = _feat_flags(feat)
            prev = tracked.get(eid)
            if prev is None:
                counts["done"] += 1
            else:
                counts["investors"] -= prev[0]
                counts["startups"] -= prev[1]
                counts["ai_tagged"] -= prev[2]
            tracked[eid] = flags
            counts["investors"] += flags[0]
            counts["startups"] += flags[1]
            counts["ai_tagged"] += flags[2]

        async def finalize_feature(eid, feat):
            final = await _tag_features_with_llm(feat, resolved_llm, llm_sem)
            async with state_lock:
                if lock_lost_error[0] is not None:
                    raise lock_lost_error[0]
                _refresh_lock(kv, token, lock_ttl=effective_lock_ttl)
                kv.set(f"{FEAT_PREFIX}{eid}", _json_dump(final), TTL_S)
                kv.delete(f"{FAILED_PREFIX}{eid}")
                if eid in todo_set:
                    todo_set.remove(eid)
                    todo[:] = [x for x in todo if x != eid]
                _apply_feature_counts(eid, final)
                status.update(counts)
                status["total"] = len(attendees)
                _save_state(kv, status, todo)

        async def process_one(eid):
            async with state_lock:
                if payment_breaker["tripped"] or lock_lost_error[0] is not None:
                    return
            attendee = attendees.get(eid) or {"id": eid, "name": eid, "type": "Company"}
            data = None
            error_status = None
            error_exc = None
            try:
                for attempt in range(5):
                    try:
                        async with cala_sem:
                            async with state_lock:
                                if payment_breaker["tripped"] or lock_lost_error[0] is not None:
                                    if lock_lost_error[0] is not None:
                                        raise lock_lost_error[0]
                                    return
                            data = await cala.retrieve(eid, properties=STAGE2_PROPERTIES, relationships=STAGE2_RELATIONSHIPS)
                        break
                    except httpx.HTTPStatusError as exc:
                        code = exc.response.status_code
                        if code == 402 and attempt < 4:
                            base = min(300.0, max(0.0, float(os.getenv("CATALOG_402_WAIT", "30"))))
                            wait = _retry_after_seconds(exc)
                            remaining = min(300.0, wait if wait is not None else base * (2 ** attempt))
                            chunk = max(0.01, float(effective_lock_ttl) / 3.0 - 0.01)
                            while remaining > 0:
                                delay = min(chunk, remaining)
                                await _sleep(delay)
                                remaining -= delay
                                async with state_lock:
                                    if lock_lost_error[0] is not None:
                                        raise lock_lost_error[0]
                                    if payment_breaker["tripped"]:
                                        return
                                    _refresh_lock(kv, token, lock_ttl=effective_lock_ttl)
                            continue
                        if code in (402, 404):
                            error_status = code
                            error_exc = exc
                            break
                        raise
            except Exception as exc:
                logger.warning("Fallo Stage 2 en Cala para %s: %s", eid, exc)
                async with state_lock:
                    status["errors"] = int(status.get("errors") or 0) + 1
                    _save_state(kv, status, todo, lock_token=token, lock_ttl=effective_lock_ttl)
                return
            if error_status is not None:
                error = str(error_exc)
                async with state_lock:
                    if payment_breaker["tripped"]:
                        return
                    if error_status == 402:
                        payment_breaker["consecutive"] += 1
                        if payment_breaker["consecutive"] >= payment_trip:
                            payment_breaker["tripped"] = True
                            status["stopped"] = "payment_required"
                            status["stage"] = "paused"
                            logger.error("Catálogo pausado: %s entidades consecutivas devolvieron 402; quedan %s pendientes.", payment_trip, len(todo))
                    kv.set(f"{FAILED_PREFIX}{eid}", _json_dump({"status": error_status, "error": error, "at": datetime.now(timezone.utc).isoformat()}), TTL_S)
                    status["errors"] = int(status.get("errors") or 0) + 1
                    counter = "payment_required" if error_status == 402 else "not_found"
                    status[counter] = int(status.get(counter) or 0) + 1
                    _save_state(kv, status, todo, lock_token=token, lock_ttl=effective_lock_ttl)
                return
            async with state_lock:
                if payment_breaker["tripped"]:
                    return
                payment_breaker["consecutive"] = 0
            center_node, edges, neighbor_nodes, truncated, base_feat = _extract_attendee_artifacts(
                attendee, data or {}, today=today,
            )
            async with state_lock:
                if lock_lost_error[0] is not None:
                    raise lock_lost_error[0]
                _refresh_lock(kv, token, lock_ttl=effective_lock_ttl)
                _save_expansion(store, center_node, edges, neighbor_nodes, rels=STAGE2_RELS, truncated=truncated)
                kv.set(f"{FEAT_PREFIX}{eid}", _json_dump(base_feat), TTL_S)
                kv.delete(f"{FAILED_PREFIX}{eid}")
                if base_feat.get("description") and resolved_llm is not None:
                    tag_tasks.append(asyncio.create_task(finalize_feature(eid, base_feat)))
                    return
                if eid in todo_set:
                    todo_set.remove(eid)
                    todo[:] = [x for x in todo if x != eid]
                _apply_feature_counts(eid, base_feat)
                status.update(counts)
                status["total"] = len(attendees)
                _save_state(kv, status, todo)

        await asyncio.gather(*(process_one(eid) for eid in work_ids))
        if tag_tasks:
            await asyncio.gather(*tag_tasks)

        if lock_lost_error[0] is not None:
            raise lock_lost_error[0]
        if payment_breaker["tripped"]:
            status["stage"] = "paused"
            _save_state(kv, status, todo, lock_token=token, lock_ttl=effective_lock_ttl)
            return status
        counts = _count_stats(kv)
        status.update(counts)
        status["total"] = len(attendees)
        status["stage"] = "done" if not todo else "partial"
        _save_state(kv, status, todo, lock_token=token, lock_ttl=effective_lock_ttl)
        return status
    finally:
        stop_heartbeat.set()
        if not heartbeat_task.done():
            heartbeat_task.cancel()
        await asyncio.gather(heartbeat_task, return_exceptions=True)
        for task in tag_tasks:
            if not task.done():
                task.cancel()
        if tag_tasks:
            await asyncio.gather(*tag_tasks, return_exceptions=True)
        kv.delete_if_equals(LOCK_KEY, token)
        if owned_http is not None:
            await owned_http.aclose()


def _dump_graph(kv, store):
    nodes, edges = [], []
    if hasattr(kv, "scan_prefix"):
        nkeys = sorted(kv.scan_prefix(f"{GRAPH_PREFIX}node:"))
        ekeys = sorted(kv.scan_prefix(f"{GRAPH_PREFIX}edge:"))
        if nkeys:
            nodes = [n for n in (_json_load(v) for v in kv.mget(nkeys)) if isinstance(n, dict)]
        if ekeys:
            edges = [e for e in (_json_load(v) for v in kv.mget(ekeys)) if isinstance(e, dict)]
    if not nodes and hasattr(store, "nodes") and isinstance(store.nodes, dict):
        nodes = list(store.nodes.values())
    if not edges and hasattr(store, "edges") and isinstance(store.edges, dict):
        edges = list(store.edges.values())
    return nodes, edges


def export_catalog(path, *, kv=None, store=None):
    """Exporta características, estado y grafo local a un archivo JSON UTF-8 sin BOM."""
    load_env()
    kv, store = _resolve_kv_and_store(kv=kv, store=store)
    feat_keys = sorted(kv.scan_prefix(FEAT_PREFIX))
    raw_feats = kv.mget(feat_keys) if feat_keys else []
    features = [f for f in (_json_load(v) for v in raw_feats) if isinstance(f, dict)]
    status = _json_load(kv.get(STATUS_KEY)) or {}
    todo = _json_load(kv.get(TODO_KEY)) or []
    attendees = _json_load(kv.get(ATTENDEES_KEY)) or {}
    nodes, edges = _dump_graph(kv, store)
    payload = {
        "version": 1,
        "exported_at": _now_iso(),
        "status": status,
        "todo": todo,
        "attendees": attendees,
        "features": features,
        "graph": {"nodes": nodes, "edges": edges},
    }
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"features": len(features), "nodes": len(nodes), "edges": len(edges), "path": str(target)}


def import_catalog(path, *, kv=None, store=None):
    """Restaura características, estado y grafo desde un JSON exportado (Plan B de demo)."""
    load_env()
    kv, store = _resolve_kv_and_store(kv=kv, store=store)
    payload = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    features = payload.get("features") or []
    if isinstance(features, dict):
        features = list(features.values())
    for feat in features:
        if isinstance(feat, dict) and feat.get("id"):
            kv.set(f"{FEAT_PREFIX}{feat['id']}", _json_dump(feat), TTL_S)
    if "status" in payload and isinstance(payload["status"], dict):
        kv.set(STATUS_KEY, _json_dump(payload["status"]), TTL_S)
    if "todo" in payload and isinstance(payload["todo"], list):
        kv.set(TODO_KEY, _json_dump(payload["todo"]), TTL_S)
    if "attendees" in payload and isinstance(payload["attendees"], dict):
        kv.set(ATTENDEES_KEY, _json_dump(payload["attendees"]), TTL_S)
    graph = payload.get("graph") or {}
    nodes = [n for n in (graph.get("nodes") or []) if isinstance(n, dict) and n.get("id")]
    edges = [e for e in (graph.get("edges") or []) if isinstance(e, dict) and e.get("src") and e.get("dst")]
    if hasattr(store, "put_node") and hasattr(store, "put_edge"):
        for node in nodes:
            store.put_node(node)
        for edge in edges:
            store.put_edge(edge)
    elif hasattr(store, "add_node") and hasattr(store, "add_edge"):
        for node in nodes:
            store.add_node(node)
        for edge in edges:
            store.add_edge(edge)
    return {"features": len(features), "nodes": len(nodes), "edges": len(edges), "path": str(path)}
