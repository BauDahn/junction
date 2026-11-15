"""Canonizer benchmark: same question in multiple phrasings, direct vs. canonicalized.

  uv run python bench.py            # runs (resumable: everything is cached) and writes bench/results.json
Direct mode: send the text as-is to knowledge_search. Canonicalized mode: canonizador.api.answer().
"""
import asyncio, hashlib, json, sys, time
from pathlib import Path

from canonizador.api import answer, _env
from canonizador.client import CalaClient

HERE = Path(__file__).parent
OUT = HERE / "bench" / "results.json"


def h(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:10]


async def run():
    _env()
    groups = json.loads((HERE / "bench" / "questions.json").read_text())
    cala = CalaClient(cache_dir=HERE / "cache")
    results = json.loads(OUT.read_text()) if OUT.exists() else {}
    for group in groups:
        g = results.setdefault(group["group"], {"direct": {}, "canonical": {}})
        for q in group["questions"]:
            if q not in g["direct"]:
                before, t = cala.calls, time.monotonic()
                try:
                    r = await cala.search(q)
                    g["direct"][q] = {"fact_ids": sorted(c["id"] for c in r.get("context") or []),
                                      "entity_ids": sorted(e["id"] for e in r.get("entities") or []),
                                      "answer_hash": h(r.get("content")), "answer": (r.get("content") or "")[:400],
                                      "calls": cala.calls - before, "seconds": round(time.monotonic() - t, 1)}
                except Exception as exc:  # do not stop the benchmark because of one call
                    g["direct"][q] = {"error": str(exc)[:300]}
                OUT.write_text(json.dumps(results, ensure_ascii=False, indent=1))
                print("direct   ", q[:60], g["direct"][q].get("seconds", "ERR"), file=sys.stderr, flush=True)
            g.setdefault("nl_query", {})
            if q not in g["nl_query"]:
                # Natural language sent as-is to knowledge/query (no guide, no template).
                before, t = cala.calls, time.monotonic()
                try:
                    r = await cala.knowledge_query(q)
                    rows = r.get("results") or []
                    g["nl_query"][q] = {"rows_hash": h(rows), "rows": rows,
                                        "names": sorted({str(x.get("name") or x.get("company") or "") for x in rows if isinstance(x, dict)}),
                                        "entity_ids": sorted(e["id"] for e in r.get("entities") or []),
                                        "calls": cala.calls - before, "seconds": round(time.monotonic() - t, 1)}
                except Exception as exc:
                    g["nl_query"][q] = {"error": str(exc)[:300]}
                OUT.write_text(json.dumps(results, ensure_ascii=False, indent=1))
                print("nl_query ", q[:60], g["nl_query"][q].get("seconds", "ERR"), file=sys.stderr, flush=True)
            if q not in g["canonical"]:
                t = time.monotonic()
                try:
                    a = await answer(q)
                    res = a.get("result") or {}
                    g["canonical"][q] = {"query": res.get("query"), "rows_hash": h(res.get("rows")), "rows": res.get("rows"),
                                         "cross_check": res.get("cross_check"), "structured_error": res.get("structured_error"),
                                         "intent": a.get("intent"), "calls": a.get("cala_calls"), "cache_hit": a.get("cache_hit"),
                                         "seconds": round(time.monotonic() - t, 1)}
                except Exception as exc:
                    g["canonical"][q] = {"error": str(exc)[:300]}
                OUT.write_text(json.dumps(results, ensure_ascii=False, indent=1))
                print("canonical", q[:60], g["canonical"][q].get("seconds", "ERR"), file=sys.stderr, flush=True)
    print(OUT)


if __name__ == "__main__":
    asyncio.run(run())
