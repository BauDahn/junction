"""Measures how long it takes to fetch a Cala subgraph (cold) and explore it locally. Read-only.
Usage (from canonizador/): MIN_INTERVAL=0.7 PYTHONPATH=. uv run python medir_subgrafo.py "Amenitiz" Company 8 /tmp/subgrafo.json
MIN_INTERVAL is the pause between calls in seconds (default 8). Measured on Nov 14: 185 nodes in 162 s with 8 and in 74 s without a pause (with one 429)."""
import asyncio, json, os, sys, time, tempfile
from collections import deque, Counter

os.environ["VALKEY_URL"] = ""  # no shared cache: measure cold timings
import httpx
from canonizador.client import CalaClient

SEED, TYPE, MAX_EXP, OUT = sys.argv[1], sys.argv[2], int(sys.argv[3]), sys.argv[4]
HUBS = {"HAS_DOMAIN_NAME", "HAS_HEADQUARTERS_IN", "IS_REGISTERED_IN", "OPERATES_IN_INDUSTRY"}
raw = []  # (method, short path, seconds, status)
_t0 = {}

async def on_req(r): _t0[id(r)] = time.perf_counter()
async def on_resp(r):
    await r.aread()
    dt = time.perf_counter() - _t0.pop(id(r.request), time.perf_counter())
    path = r.request.url.path.replace("/v1", "")
    kind = "introspection" if path.endswith("introspection") else ("search" if r.request.method == "GET" else "retrieve")
    raw.append((kind, round(dt, 2), r.status_code, len(r.content)))
    print(f"  {kind:14s} {dt:6.1f}s  http {r.status_code}  {len(r.content)/1024:7.1f} KB", flush=True)

def names(x):
    return [i if isinstance(i, str) else (i.get("name") or i.get("type") or "") for i in (x or [])] if not isinstance(x, dict) else list(x)

async def expand(cala, eid):
    intro = await cala.introspection(eid)
    rels = intro.get("relationships", {}) or {}
    req = {d: {r: {"limit": 100} for r in names(rels.get(d)) if r and r not in HUBS} for d in ("incoming", "outgoing")}
    req = {d: v for d, v in req.items() if v}
    data = await cala.retrieve(eid, properties=["name"], relationships=req)
    edges = []
    for d, by in (data.get("relationships", {}) or {}).items():
        for rel, items in (by or {}).items():
            for it in items or []:
                if isinstance(it, dict) and it.get("id"):
                    edges.append({"a": eid, "b": it["id"], "rel": rel, "dir": d, "name": it.get("name"),
                                  "type": it.get("entity_type"), "role": (it.get("properties") or {}).get("role"), "n_sources": len((it.get("properties") or {}).get("sources") or [])})
    return edges

async def main():
    t_start = time.perf_counter()
    async with httpx.AsyncClient(timeout=120, event_hooks={"request": [on_req], "response": [on_resp]}) as http:
        with tempfile.TemporaryDirectory(prefix="cala-medir-") as cache:
            cala = CalaClient(cache_dir=cache, client=http, min_interval=float(os.getenv("MIN_INTERVAL", "8")))
            found = await cala.entities(SEED, TYPE)
            items = found.get("entities") or found.get("results") or (found if isinstance(found, list) else [])
            seed = items[0]
            sid = seed.get("id") or seed.get("entity_id")
            nodes = {sid: {"name": seed.get("name", SEED), "type": TYPE, "level": 0}}
            edges, levels = [], []
            t = time.perf_counter()
            print(f"nivel 0: {nodes[sid]['name']}", flush=True)
            e0 = await expand(cala, sid); edges += e0
            for e in e0: nodes.setdefault(e["b"], {"name": e["name"], "type": e["type"], "level": 1})
            levels.append({"level": 0, "expanded": 1, "seconds": round(time.perf_counter() - t, 1), "new_edges": len(e0)})
            # nivel 1: reparto parejo entre tipos de entidad
            by_type = {}
            for nid, n in nodes.items():
                if n["level"] == 1: by_type.setdefault(n["type"], []).append(nid)
            order = []
            while len(order) < MAX_EXP and any(by_type.values()):
                for k in list(by_type):
                    if by_type[k] and len(order) < MAX_EXP: order.append(by_type[k].pop(0))
            t = time.perf_counter(); new = 0
            for nid in order:
                print(f"nivel 1: {nodes[nid]['name']} ({nodes[nid]['type']})", flush=True)
                try: es = await expand(cala, nid)
                except Exception as ex:
                    print("  error:", type(ex).__name__, str(ex)[:120], flush=True); continue
                edges += es; new += len(es)
                for e in es: nodes.setdefault(e["b"], {"name": e["name"], "type": e["type"], "level": 2})
            levels.append({"level": 1, "expanded": len(order), "seconds": round(time.perf_counter() - t, 1), "new_edges": new})
            total = round(time.perf_counter() - t_start, 1)
            json.dump({"seed": sid, "nodes": nodes, "edges": edges, "levels": levels, "raw": raw, "total_s": total, "calls": cala.calls},
                      open(OUT, "w"), ensure_ascii=False)
    print("\n== CARGA DESDE CALA ==")
    print(f"total {total}s, {len(raw)} HTTP calls, {len(nodes)} nodes, {len(edges)} edges")
    for lv in levels: print(" ", lv)
    for k in ("search", "introspection", "retrieve"):
        v = sorted(x[1] for x in raw if x[0] == k and x[2] == 200)
        if v: print(f"  {k:14s} n={len(v)} min={v[0]} mediana={v[len(v)//2]} max={v[-1]}")
    print("  http:", dict(Counter(x[2] for x in raw)), " KB totales:", round(sum(x[3] for x in raw) / 1024))
    print("  tipos de nodo:", dict(Counter(n["type"] for n in nodes.values())))
    print("  tipos de arista:", dict(Counter(e["rel"] for e in edges)))
    print("  nodes by level:", dict(Counter(n["level"] for n in nodes.values())))
    local(OUT)

def bfs(adj, s):
    dist, prev, q = {s: 0}, {}, deque([s])
    while q:
        u = q.popleft()
        for v in adj.get(u, ()):
            if v not in dist: dist[v] = dist[u] + 1; prev[v] = u; q.append(v)
    return dist, prev

def bench(f, n):
    t = time.perf_counter()
    for _ in range(n): f()
    return (time.perf_counter() - t) / n * 1000

def local(path):
    import random
    t = time.perf_counter(); g = json.load(open(path)); load_ms = (time.perf_counter() - t) * 1000
    adj = {}
    for e in g["edges"]:
        adj.setdefault(e["a"], set()).add(e["b"]); adj.setdefault(e["b"], set()).add(e["a"])
    s = g["seed"]
    dist, prev = bfs(adj, s)
    far = max(dist, key=dist.get)
    print("\n== LOCAL EXPLORATION ==")
    print(f"  read JSON from disk: {load_ms:.2f} ms ({os.path.getsize(path)/1024:.0f} KB)")
    print(f"  Full BFS from the seed ({len(dist)} nodes reached, max distance {dist[far]}): {bench(lambda: bfs(adj, s), 200):.3f} ms")
    def path_to():
        d, p = bfs(adj, s); out = [far]
        while out[-1] != s: out.append(p[out[-1]])
        return out
    print(f"  shortest path from seed → farthest node: {bench(path_to, 200):.3f} ms")
    names_ = [g["nodes"][n]["name"] for n in reversed(path_to())]
    print("    ejemplo:", " → ".join(str(x) for x in names_))
    f = lambda: [n for n, d in dist.items() if d <= 2 and g["nodes"][n]["type"] == "Person"]
    print(f"  filtrar personas a distancia ≤ 2: {bench(f, 200):.3f} ms ({len(f())} resultados)")
    # same algorithm on a large synthetic graph, to see whether size is a problem
    for n_nodes, deg in ((10_000, 6), (100_000, 6)):
        random.seed(1); big = {i: set() for i in range(n_nodes)}
        for i in range(n_nodes):
            for _ in range(deg // 2):
                j = random.randrange(n_nodes); big[i].add(j); big[j].add(i)
        print(f"  synthetic {n_nodes} nodes / {sum(map(len, big.values()))//2} edges: full BFS {bench(lambda: bfs(big, 0), 3):.1f} ms")

if __name__ == "__main__":
    if SEED == "--local": local(OUT)
    else: asyncio.run(main())
