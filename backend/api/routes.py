"""Endpoints del feed y detalle de Cala Match."""
import asyncio
import base64
import json
import unicodedata
from collections import Counter
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from chat import store as chat_store
from .affinity import format_amount, rank
from . import enrich
from .candidates import build_feed, candidate_for_entity
from .catalog_port import get_catalog
from .graph_port import get_graph, neighbors_batch

router = APIRouter()
_cala = None


def get_cala():
    global _cala
    if _cala is None:
        try:
            from canonizador.client import CalaClient
            from core.config import settings
            if not settings.cala_api_key:
                return None
            _cala = CalaClient(settings.cala_api_key, settings.cache_dir)
        except Exception:
            return None
    return _cala


def _session(session_id):
    if not chat_store.session_exists(session_id):
        raise HTTPException(404, "Session not found.")


def _mode(mode, session_id=None):
    current = mode or (chat_store.get_mode(session_id) if session_id else None) or "raising"
    if current not in ("raising", "investing"):
        raise HTTPException(422, "Mode must be raising or investing.")
    return current


def _union(*groups, limit=8):
    output = []
    seen = set()
    for group in groups:
        for source in group or []:
            if not isinstance(source, dict):
                continue
            key = source.get("url") or source.get("name") or json.dumps(source, sort_keys=True)
            if key in seen:
                continue
            seen.add(key)
            output.append(source)
            if len(output) >= limit:
                return output
    return output


def _one_liner(description):
    if not description:
        return ""
    if len(description) <= 160:
        return description
    excerpt = description[:160]
    if " " in excerpt:
        excerpt = excerpt.rsplit(" ", 1)[0]
    return excerpt.rstrip() + "…"


def _feedcard(result):
    candidate = result["_candidate"]
    features = result.get("_features") or {}
    sources = candidate.get("attrs", {}).get("sources", [])
    ai_tagged = features.get("ai_tagged", False)
    tags = []
    if features.get("sources"):
        for sector in features.get("sectors", [])[:2]:
            suffix = " (AI-tagged)" if ai_tagged is True or isinstance(ai_tagged, list) and "sectors" in ai_tagged else ""
            tags.append(str(sector) + suffix)
        stages = features.get("stages", [])
        if stages:
            suffix = " (AI-tagged)" if ai_tagged is True or isinstance(ai_tagged, list) and "stages" in ai_tagged else ""
            tags.append(str(stages[0]) + suffix)
        if features.get("country"):
            tags.append(features["country"])
    why_match = result.get("why_match", [])
    return {"id": result["id"], "type": result["type"], "name": result["name"],
            "one_liner": _one_liner(features.get("description") if features.get("sources") else ""),
            "tags": tags, "score": result["score"], "confidence": result["confidence"],
            "why_match": [signal["text"] for signal in why_match],
            "sources": _union(sources, *(signal["sources"] for signal in why_match))}


def _cursor_key(result):
    return (-result["score"], -result["confidence"], result["name"].casefold(), str(result["id"]))


def _encode_cursor(result):
    payload = [result["score"], result["confidence"], result["name"].casefold(), str(result["id"])]
    raw = json.dumps(payload, separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _decode_cursor(cursor):
    try:
        padding = "=" * ((4 - len(cursor) % 4) % 4)
        values = json.loads(base64.urlsafe_b64decode(cursor + padding))
        if not isinstance(values, list) or len(values) != 4:
            raise ValueError
        return -int(values[0]), -float(values[1]), str(values[2]), str(values[3])
    except Exception as exc:
        raise HTTPException(422, "Invalid cursor.") from exc


@router.get("/api/feed")
async def feed(session_id: str = Query(...), mode: str | None = None,
               limit: int = Query(20, ge=1, le=100), cursor: str | None = None,
               catalog=Depends(get_catalog), graph=Depends(get_graph), cala=Depends(get_cala)):
    _session(session_id)
    current_mode = _mode(mode, session_id)
    profile = chat_store.get_profile(session_id) or {}
    result = await asyncio.to_thread(build_feed, session_id, profile, current_mode, catalog, graph)
    rows = rank(result["results"])
    if cursor:
        key = _decode_cursor(cursor)
        rows = [row for row in rows if _cursor_key(row) > key]
    page = rows[:limit]
    cards = [_feedcard(row) for row in page]
    if current_mode == "raising":
        enrich.schedule(result["results"], cala)
    output = {"mode": current_mode, "items": cards}
    if len(rows) > limit and page:
        output["next_cursor"] = _encode_cursor(page[-1])
    if result["note"]:
        output["confidence_note"] = result["note"]
    return output


def _entity_type(features, node, edges, mode):
    kinds = features.get("kinds", []) if features else []
    if len(kinds) == 1:
        return kinds[0]
    if len(kinds) > 1:
        return "investor" if mode == "raising" else "startup"
    if node:
        ident = str(node.get("id"))
        is_investor = any(edge.get("rel") == "INVESTED_IN" and str(edge.get("src")) == ident
                          for edge, _ in edges)
        is_startup = any(
            (edge.get("rel") == "INVESTED_IN" and str(edge.get("dst")) == ident)
            or (edge.get("rel") == "PARTICIPATES_IN_FUNDING_ROUND"
                and str(edge.get("src")) == ident and edge.get("role") == "ISSUER")
            for edge, _ in edges)
        if is_investor and is_startup:
            return "investor" if mode == "raising" else "startup"
        if is_investor:
            return "investor"
        if is_startup:
            return "startup"
    return "investor" if mode == "raising" else "startup"


def _detail_sync(entity_id, session_id, profile, mode, catalog, graph):
    features = catalog.get_features(entity_id)
    node = graph.get_node(entity_id)
    edges = neighbors_batch(graph, [entity_id]).get(str(entity_id), []) if node else []
    if not features and not node:
        raise HTTPException(404, "Entity not found.")
    entity_type = _entity_type(features, node, edges, mode)
    name = features.get("name") if features else node.get("name")
    props = node.get("props") or {} if node else {}
    node_sources = props.get("sources") or node.get("sources", []) if node else []
    if not node_sources and props:
        node_sources = _union(*(value.get("sources", []) for value in props.values() if isinstance(value, dict)))
    feature_sources = features.get("sources", []) if features else []
    sources = feature_sources or node_sources
    detail = {"id": entity_id, "type": entity_type, "name": name, "why_match": [], "facts": [],
              "rounds": [], "portfolio": [], "people": [],
              "loaded_at": features.get("loaded_at") if features else node.get("loaded_at")}
    description = features.get("description") if features else props.get("description")
    if isinstance(description, dict):
        description = description.get("value")
    if description and sources:
        detail["description"] = description

    def add_fact(label, value):
        if value is not None and value != "" and feature_sources:
            detail["facts"].append({"label": label, "value": str(value), "sources": feature_sources})

    if features and feature_sources:
        ai_tagged = features.get("ai_tagged", False)
        sector_label = "Sectors (AI-tagged)" if ai_tagged is True or isinstance(ai_tagged, list) and "sectors" in ai_tagged else "Sectors"
        stage_label = "Stages (AI-tagged)" if ai_tagged is True or isinstance(ai_tagged, list) and "stages" in ai_tagged else "Stages"
        add_fact(sector_label, ", ".join(features["sectors"]) if features["sectors"] else None)
        add_fact(stage_label, ", ".join(features["stages"]) if features["stages"] else None)
        add_fact("Headquarters", features.get("hq"))
        add_fact("Country", features.get("country"))
        amount = features.get("amount") or {}
        low = amount.get("min")
        high = amount.get("max")
        if low is not None or high is not None:
            if low is not None and high is not None and low == high:
                size = format_amount(low)
            else:
                size = format_amount(low if low is not None else high)
            if high is not None and low is not None and low != high:
                size += "–" + format_amount(high)
            add_fact("Typical round size", size)
        activity = features.get("activity") or {}
        add_fact("Rounds in the last 24 months", activity.get("rounds_24m"))
        add_fact("Rounds led in the last 24 months", activity.get("led_24m"))

    rounds = features.get("rounds", []) if features else []
    if not rounds:
        rounds = enrich.rounds_for(entity_id)
    if entity_type == "investor":
        for round_data in rounds:
            round_sources = round_data.get("sources") or []
            if not round_sources:
                continue
            item = {}
            fields = (("round_type", "round_type"), ("funding_amount", "amount"), ("year", "date"))
            for source_key, target_key in fields:
                if round_data.get(source_key) is not None:
                    item[target_key] = str(round_data[source_key])
            item["leads"] = [name] if round_data.get("is_lead") else []
            item["investors"] = [name]
            item["sources"] = round_sources
            detail["rounds"].append(item)
    elif rounds:
        for round_data in rounds:
            round_sources = round_data.get("sources") or []
            if not round_sources:
                continue
            item = {}
            fields = (("round_type", "round_type"), ("funding_amount", "amount"), ("year", "date"))
            for source_key, target_key in fields:
                if round_data.get(source_key) is not None:
                    item[target_key] = str(round_data[source_key])
            item["leads"] = list(round_data.get("leads") or [])
            item["investors"] = list(round_data.get("investors") or [])
            item["sources"] = round_sources
            detail["rounds"].append(item)
    else:
        grouped = {}
        for edge, neighbor in edges:
            if edge.get("rel") != "INVESTED_IN" or str(edge.get("dst")) != entity_id or not edge.get("sources"):
                continue
            event_date = edge.get("event_date")
            key = str(event_date) if event_date else "__undated__"
            initial = {"date": str(event_date)} if event_date else {}
            initial.update({"leads": [], "investors": [], "sources": []})
            group = grouped.setdefault(key, initial)
            group["investors"].append(neighbor.get("name"))
            if edge.get("is_lead"):
                group["leads"].append(neighbor.get("name"))
            group["sources"] = _union(group["sources"], edge.get("sources"))
        detail["rounds"] = list(grouped.values())

    roles = {"FOUNDED": "Founder", "IS_CEO_OF": "CEO", "IS_CTO_OF": "CTO",
             "IS_BOARD_MEMBER_OF": "Board member", "WORKS_AT": "Employee", "IS_MEMBER_OF": "Member"}
    for edge, neighbor in edges:
        if not edge.get("sources"):
            continue
        if edge.get("rel") == "INVESTED_IN" and str(edge.get("src")) == entity_id:
            detail["portfolio"].append({"id": str(neighbor["id"]), "name": neighbor.get("name")})
        role = roles.get(edge.get("rel"))
        if role and str(edge.get("dst")) == entity_id:
            person = {"id": str(neighbor["id"]), "name": neighbor.get("name"), "role": role}
            if edge.get("valid_since"):
                person["since"] = edge["valid_since"]
            detail["people"].append(person)

    if session_id:
        scored = candidate_for_entity(entity_id, session_id, profile, mode, catalog, graph)
        if scored:
            detail["score"] = scored["score"]
            detail["confidence"] = scored["confidence"]
            signals = [signal for signal in scored["signals"]
                       if signal["value"] is not None and signal["sources"]]
            signals.sort(key=lambda signal: signal["weight"] * signal["value"], reverse=True)
            detail["why_match"] = [{"signal": signal["signal"], "text": signal["text"],
                                     "sources": signal["sources"]} for signal in signals]
    return detail


@router.get("/api/entities/{entity_id}")
async def entity(entity_id: str, mode: str | None = None, session_id: str | None = None,
                 catalog=Depends(get_catalog), graph=Depends(get_graph), cala=Depends(get_cala)):
    current_mode = _mode(mode, session_id)
    if session_id:
        _session(session_id)
    profile = chat_store.get_profile(session_id) or {} if session_id else {}
    if not catalog.get_features(entity_id) and not graph.get_node(entity_id):
        if cala is None:
            raise HTTPException(404, "Entity not found in the graph or in Cala.")
        from graph.loader import expand_node
        stats = {"nodes": set(), "edges": set(), "cala_calls": 0, "skipped_expanded": 0,
                 "excluded": Counter(), "truncated": [], "errors": [], "levels": []}
        try:
            expanded = await asyncio.wait_for(expand_node(graph, cala, entity_id, stats), timeout=25)
        except asyncio.TimeoutError as exc:
            raise HTTPException(504, "Cala did not answer in time.") from exc
        except Exception as exc:
            if exc.__class__.__name__ == "CalaBudgetExceeded":
                raise HTTPException(503, "Cala call cap reached.") from exc
            raise
        if expanded is None:
            errors = stats.get("errors") or []
            message = " ".join(str(error.get("error", "")) for error in errors if isinstance(error, dict)).casefold()
            if "daily cala call cap reached" in message:
                raise HTTPException(503, "Cala call cap reached.")
            missing = any(token in message for token in ("not found", "not exist", "unknown entity", "404", "doesn't exist"))
            missing = missing or any(str(error.get("error", "")).strip("'\"") == str(entity_id)
                                     for error in errors if isinstance(error, dict))
            if missing:
                raise HTTPException(404, "Entity not found in the graph or in Cala.")
            raise HTTPException(502, "Cala request failed.")
        if not graph.get_node(entity_id):
            raise HTTPException(404, "Entity not found in the graph or in Cala.")
        node = graph.get_node(entity_id)
        node["loaded_at"] = datetime.now(timezone.utc).isoformat()
    return await asyncio.to_thread(_detail_sync, entity_id, session_id, profile, current_mode, catalog, graph)


def _fold_name(value):
    return "".join(ch for ch in unicodedata.normalize("NFD", str(value or "").casefold())
                   if unicodedata.category(ch) != "Mn")


@router.get("/api/search")
async def search(q: str = Query(..., min_length=2, max_length=80), limit: int = Query(8, ge=1, le=50),
                 catalog=Depends(get_catalog), cala=Depends(get_cala)):
    needle = _fold_name(q)
    local, seen = [], set()
    for kind in ("investor", "startup"):
        for feature in catalog.list_features(kind):
            ident = str(feature.get("id", ""))
            name = feature.get("name", "")
            if ident and ident not in seen and needle in _fold_name(name):
                seen.add(ident)
                local.append({"id": ident, "name": name, "type": kind, "origin": "catalog",
                              **({"one_liner": _one_liner(feature.get("description"))} if feature.get("description") else {})})
    items = local[:limit]
    tried = ["catalog"]
    if len(items) < limit and cala is not None:
        tried.append("cala")
        async def get_entities(kind):
            try:
                result = await cala.entities(q, kind)
                return result if isinstance(result, list) else result.get("entities", []) if isinstance(result, dict) else []
            except Exception:
                return []
        results = await asyncio.gather(get_entities("Company"), get_entities("Organization"))
        for group in results:
            for entity_data in group:
                if not isinstance(entity_data, dict):
                    continue
                ident, name = entity_data.get("id"), entity_data.get("name")
                if not ident or not name or str(ident) in seen:
                    continue
                seen.add(str(ident))
                items.append({"id": str(ident), "name": name, "type": "other", "origin": "cala"})
                if len(items) >= limit:
                    break
            if len(items) >= limit:
                break
    return {"query": q, "items": items[:limit], "tried": tried}


class ModeInput(BaseModel):
    mode: str


@router.post("/api/sessions/{session_id}/mode")
async def save_mode(session_id: str, body: ModeInput):
    _session(session_id)
    current_mode = _mode(body.mode)
    from accounts.store import get_user_by_session_id
    owner = get_user_by_session_id(session_id)
    if owner and current_mode != ("raising" if owner["role"] == "raiser" else "investing"):
        raise HTTPException(409, "role_locked")
    chat_store.save_mode(session_id, current_mode)
    return {"mode": current_mode}


def _stats_snapshot(catalog, cala):
    investors = catalog.list_features("investor")
    startups = catalog.list_features("startup")
    output = {"catalog": {"investors": len(investors), "startups": len(startups),
                           "total": len({feature["id"] for feature in investors + startups}),
                           "status": catalog.status()}}
    stats = getattr(cala, "stats", None) if cala else None
    remote = getattr(getattr(cala, "cache", None), "remote", None) if cala else None
    if remote is None and cala is not None and hasattr(cala, "cache") and hasattr(cala.cache, "_run"):
        remote = cala.cache
    if remote is None:
        try:
            from canonizador.cache import remote_from_env
            remote = remote_from_env()
        except Exception:
            remote = None
    if remote is not None:
        try:
            from canonizador.client import cala_usage
            output["cala_usage"] = cala_usage(remote)
        except Exception:
            output["cala_usage"] = {}
    else:
        output["cala_usage"] = {}
    if stats is not None:
        try:
            output["cala"] = stats() if callable(stats) else stats
        except Exception:
            pass
    return output


@router.get("/api/stats")
async def stats(catalog=Depends(get_catalog), cala=Depends(get_cala)):
    return await asyncio.to_thread(_stats_snapshot, catalog, cala)
