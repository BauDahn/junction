"""Candidatos inversores reconstruidos desde las carteras del catálogo."""
import os
import math
import re
import threading
import time

from .graph_port import neighbors_batch

_LOCK = threading.Lock()
_CACHE = {}


def apply_evidence(result, candidate):
    """Ajusta el puntaje según la cantidad de participaciones trazables."""
    if "deals" not in candidate:
        return result
    deals = candidate["deals"]
    factor = min(1, 0.6 + 0.4 * math.log2(1 + deals) / math.log2(10))
    result = dict(result)
    result["score"] = round(result["score"] * factor)
    if factor < 1:
        signal = {"signal": "evidence", "value": factor, "weight": 0,
                  "text": f"Based on {deals} tracked deal(s) with Slush attendees; score scaled to {factor:.2f}",
                  "sources": list((candidate.get("attrs") or {}).get("sources") or [])}
        result["signals"] = list(result.get("signals") or []) + [signal]
        result["why_match"] = list(result.get("why_match") or []) + [dict(signal)]
    return result


def reset():
    """Limpia la caché del pool para pruebas."""
    with _LOCK:
        _CACHE.clear()


def portfolio_investors(catalog, store):
    """Agrupa inversores con participaciones trazables en startups asistentes."""
    startups = catalog.list_features("startup")
    startup_ids = [str(feature["id"]) for feature in startups if feature.get("id")]
    key = (id(catalog), id(store), tuple(startup_ids), os.getenv("INVESTOR_POOL_PERSONS", "0"),
           os.getenv("INVESTOR_POOL_MIN_DEALS", "1"))
    ttl = max(0, int(os.getenv("INVESTOR_POOL_TTL_S", "300")))
    now = time.monotonic()
    with _LOCK:
        cached = _CACHE.get(key)
        if cached and now - cached[0] < ttl:
            return [dict(item) for item in cached[1]]
        by_startup = {str(feature["id"]): feature for feature in startups if feature.get("id")}
        batch = neighbors_batch(store, startup_ids, rels=("INVESTED_IN",))
        grouped = {}
        for startup_id in startup_ids:
            startup = by_startup[startup_id]
            sectors = startup.get("sectors") or []
            location = startup.get("hq") or startup.get("country")
            for edge, node in batch.get(startup_id, []):
                investor_id = str(edge.get("src") or "")
                if (edge.get("rel") != "INVESTED_IN" or str(edge.get("dst")) != startup_id
                        or not investor_id or not edge.get("sources")):
                    continue
                entity_type = str(node.get("type") or node.get("entity_type") or "").casefold()
                if entity_type == "person" and os.getenv("INVESTOR_POOL_PERSONS", "0") != "1":
                    continue
                record = grouped.setdefault(investor_id, {
                    "id": investor_id, "name": node.get("name"), "type": "investor", "rounds": [],
                    "attrs": {"industries": [], "hq": None, "country": None, "sources": []},
                    "features": {}, "distance": None, "distance_sources": [], "deals": 0,
                })
                round_data = {"company": startup.get("name"),
                              "sector": ", ".join(str(value) for value in sectors) if sectors else None,
                              "location": location, "sources": edge.get("sources")}
                event_date = edge.get("event_date") or edge.get("valid_since")
                if event_date:
                    match = re.search(r"(?:19|20)\d{2}", str(event_date))
                    if match:
                        round_data["year"] = int(match.group())
                if "is_lead" in edge:
                    round_data["is_lead"] = edge["is_lead"]
                record["rounds"].append(round_data)
                record["deals"] += 1
                record["attrs"]["sources"].extend(edge["sources"])
        minimum = max(1, int(os.getenv("INVESTOR_POOL_MIN_DEALS", "1")))
        result = []
        for record in grouped.values():
            if record["deals"] < minimum:
                continue
            sources, seen = [], set()
            for source in record["attrs"]["sources"]:
                token = source.get("url") or source.get("name") or repr(source)
                if token not in seen:
                    seen.add(token)
                    sources.append(source)
                if len(sources) == 5:
                    break
            record["attrs"]["sources"] = sources
            result.append(record)
        _CACHE[key] = (now, result)
        return [dict(item) for item in result]
