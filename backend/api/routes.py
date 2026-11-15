"""Endpoints del feed y detalle de Cala Match."""
import asyncio
import base64
import json
import unicodedata
from collections import Counter
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, Field, field_validator
from chat import store as chat_store
from .affinity import format_amount, rank
from . import enrich
from .candidates import build_feed, candidate_for_entity
from .catalog_port import get_catalog
from .graph_port import get_graph, neighbors_batch

router = APIRouter()
_cala = None


class FavoritesReportRequest(BaseModel):
    entity_ids: list[str] = Field(min_length=1, max_length=10)
    session_id: str | None = None
    mode: str | None = None

    @field_validator("entity_ids", mode="before")
    @classmethod
    def normalize_entity_ids(cls, value):
        if isinstance(value, list):
            return list(dict.fromkeys(item.strip() for item in value if isinstance(item, str)))
        return value

    @field_validator("entity_ids")
    @classmethod
    def validate_entity_ids(cls, value):
        if any(not item or len(item) > 200 for item in value):
            raise ValueError("entity ids must be non-empty and at most 200 characters")
        return value


def get_report_llm():
    from core.llm import make_llm
    return make_llm(tier="fast")[0]


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
        investments = sum(edge.get("rel") == "INVESTED_IN" and str(edge.get("src")) == ident
                          for edge, _ in edges)
        issued_rounds = sum(edge.get("rel") == "PARTICIPATES_IN_FUNDING_ROUND"
                            and str(edge.get("src")) == ident and edge.get("role") == "ISSUER"
                            for edge, _ in edges)
        is_investor = investments > 0
        is_startup = any(edge.get("rel") == "INVESTED_IN" and str(edge.get("dst")) == ident
                         for edge, _ in edges) or issued_rounds > 0
        if issued_rounds:
            return "investor" if mode == "investing" and investments > issued_rounds else "startup"
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
              "loaded_at": (features or {}).get("loaded_at") or (node or {}).get("loaded_at")}
    description_prop = props.get("description")
    description = features.get("description") if features else (description_prop or {}).get("value") if isinstance(description_prop, dict) else None
    description_sources = (description_prop or {}).get("sources", []) if isinstance(description_prop, dict) else feature_sources
    if description and description_sources:
        detail["description"] = description

    def add_fact(label, value, fact_sources=None):
        if fact_sources is None:
            fact_sources = feature_sources
        if value is not None and value != "" and fact_sources:
            rendered = str(value)
            existing = next((fact for fact in detail["facts"] if fact["label"] == label), None)
            if existing is None:
                detail["facts"].append({"label": label, "value": rendered, "sources": _union(fact_sources, limit=10000)})
            else:
                values = list(dict.fromkeys(existing["value"].split(", ") + rendered.split(", ")))
                existing["value"] = ", ".join(values)
                existing["sources"] = _union(existing["sources"], fact_sources, limit=10000)

    def prop_value(key):
        value = props.get(key)
        return (value.get("value"), value.get("sources") or []) if isinstance(value, dict) else (None, [])

    def add_prop(label, key, transform=lambda value: value):
        value, src = prop_value(key)
        if value is not None:
            add_fact(label, transform(value), src)

    if node:
        add_prop("Website", "website")
        add_prop("Founded", "founding_date", lambda value: str(value)[:4])
        add_prop("Stage", "funding_stage", lambda value: str(value).replace("_", " ").title())
        funding, funding_sources = prop_value("total_funding")
        units, units_sources = prop_value("total_funding_units")
        if funding is not None:
            add_fact("Total funding", f"{funding} {units}".strip() if units else funding, _union(funding_sources, units_sources))
        add_prop("Employees", "employee_count_range")
        add_prop("Status", "operational_status", lambda value: str(value).replace("_", " ").title())
        for item in props.get("industries", []) if isinstance(props.get("industries"), list) else []:
            if isinstance(item, dict):
                add_fact("Industry", str(item.get("name", "")).replace("_", " ").title(), item.get("sources"))
        hq = props.get("hq")
        if isinstance(hq, dict):
            add_fact("Headquarters", hq.get("name"), hq.get("sources"))

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

    if not features:
        company_investors = [(neighbor.get("name"), bool(edge.get("is_lead")), edge.get("sources") or [])
                             for edge, neighbor in edges
                             if edge.get("rel") == "INVESTED_IN" and str(edge.get("dst")) == entity_id]
        for edge, round_ref in edges:
            if (edge.get("rel") != "PARTICIPATES_IN_FUNDING_ROUND"
                    or str(edge.get("src")) != entity_id or edge.get("role") != "ISSUER"):
                continue
            round_node = graph.get_node(round_ref.get("id")) or {}
            round_props = round_node.get("props") or {}
            round_sources = _union(edge.get("sources"), *(value.get("sources", []) for value in round_props.values() if isinstance(value, dict)))
            if not round_sources:
                continue
            def round_prop(key):
                value = round_props.get(key)
                return value.get("value") if isinstance(value, dict) else None
            rtype = round_prop("round_label") or round_prop("instrument") or round_ref.get("name")
            amount = round_prop("transaction_value")
            units = round_prop("transaction_value_units")
            date = round_prop("announcement_date") or round_prop("event_date")
            item = {"round_type": str(rtype), "leads": [], "investors": [], "sources": round_sources}
            if amount is not None:
                item["amount"] = f"{amount} {units}".strip() if units else str(amount)
            if date is not None:
                item["date"] = str(date)
            for investor_name, is_lead, investor_sources in company_investors:
                if investor_sources:
                    item["investors"].append(investor_name)
                    if is_lead:
                        item["leads"].append(investor_name)
            detail["rounds"].append(item)
        detail["rounds"].sort(key=lambda item: str(item.get("date", "")), reverse=True)

    roles = {"FOUNDED": "Founder", "IS_CEO_OF": "CEO", "IS_CTO_OF": "CTO",
             "IS_BOARD_MEMBER_OF": "Board member", "WORKS_AT": "Employee", "IS_MEMBER_OF": "Member"}
    for edge, neighbor in edges:
        if not edge.get("sources"):
            continue
        if edge.get("rel") == "INVESTED_IN" and str(edge.get("src")) == entity_id:
            portfolio_item = {"id": str(neighbor["id"]), "name": neighbor.get("name")}
            if edge.get("event_date"):
                portfolio_item["event_date"] = str(edge["event_date"])
            detail["portfolio"].append(portfolio_item)
        role = roles.get(edge.get("rel"))
        if role and str(edge.get("dst")) == entity_id:
            person = {"id": str(neighbor["id"]), "name": neighbor.get("name"), "role": role}
            if edge.get("valid_since"):
                person["since"] = edge["valid_since"]
            detail["people"].append(person)

    detail["portfolio"].sort(key=lambda item: str(item.get("event_date", "")), reverse=True)
    detail["portfolio"] = detail["portfolio"][:10]
    for item in detail["portfolio"]:
        item.pop("event_date", None)

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
    cached_node = graph.get_node(entity_id)
    expanded = bool(cached_node and getattr(graph, "is_expanded", lambda *_: False)(entity_id, "biz:v1"))
    if not expanded:
        if cala is None:
            if not catalog.get_features(entity_id) and not cached_node:
                raise HTTPException(404, "Entity not found in the graph or in Cala.")
        else:
            from graph.loader import expand_node
            stats = {"nodes": set(), "edges": set(), "cala_calls": 0, "skipped_expanded": 0,
                     "excluded": Counter(), "truncated": [], "errors": [], "levels": []}
            try:
                expanded_id = await asyncio.wait_for(expand_node(graph, cala, entity_id, stats), timeout=25)
                if expanded_id is not None:
                    issuer_rounds = [(edge, neighbor) for edge, neighbor in neighbors_batch(graph, [entity_id]).get(str(entity_id), [])
                                     if edge.get("rel") == "PARTICIPATES_IN_FUNDING_ROUND"
                                     and str(edge.get("src")) == str(entity_id) and edge.get("role") == "ISSUER"]
                    issuer_rounds.sort(key=lambda row: str(row[0].get("event_date") or ""), reverse=True)
                    for _, round_node in issuer_rounds[:3]:
                        round_id = str(round_node.get("id"))
                        if not getattr(graph, "is_expanded", lambda *_: False)(round_id, "biz:v1"):
                            await asyncio.wait_for(expand_node(graph, cala, round_id, stats), timeout=25)
                    loaded_node = graph.get_node(entity_id)
                    if loaded_node is not None:
                        loaded_node["loaded_at"] = datetime.now(timezone.utc).isoformat()
                        if hasattr(graph, "put_node"):
                            graph.put_node(loaded_node)
                        elif hasattr(graph, "add_node"):
                            graph.add_node(loaded_node)
            except asyncio.TimeoutError as exc:
                raise HTTPException(504, "Cala did not answer in time.") from exc
            except Exception as exc:
                if exc.__class__.__name__ == "CalaBudgetExceeded":
                    raise HTTPException(503, "Cala call cap reached.") from exc
                raise
        if cala is not None and not graph.get_node(entity_id):
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
        if not graph.get_node(entity_id) and not catalog.get_features(entity_id):
            raise HTTPException(404, "Entity not found in the graph or in Cala.")
    return await asyncio.to_thread(_detail_sync, entity_id, session_id, profile, current_mode, catalog, graph)


@router.post("/api/favorites/report")
async def favorites_report(body: FavoritesReportRequest, catalog=Depends(get_catalog),
                           graph=Depends(get_graph), cala=Depends(get_cala), llm=Depends(get_report_llm)):
    from .favorites_report import action_plan, render_pdf

    current_mode = _mode(body.mode, body.session_id)
    if body.session_id:
        _session(body.session_id)
    profile = chat_store.get_profile(body.session_id) or {} if body.session_id else {}

    async def create_report():
        omitted_by_index = [None] * len(body.entity_ids)
        failure_codes = [None] * len(body.entity_ids)
        entries_by_index = [None] * len(body.entity_ids)
        semaphore = asyncio.Semaphore(2)

        async def load(index, entity_id):
            async with semaphore:
                try:
                    detail = await entity(entity_id, current_mode, body.session_id, catalog, graph, cala)
                    entries_by_index[index] = {"detail": detail, "plan": None}
                except HTTPException as exc:
                    failure_codes[index] = exc.status_code
                    reason = {404: "Not found in the catalog or in Cala", 503: "Cala daily call cap reached",
                              504: "Cala did not answer in time"}.get(exc.status_code, "Cala request failed")
                    omitted_by_index[index] = {"id": entity_id, "reason": reason}
                except Exception:
                    failure_codes[index] = 502
                    omitted_by_index[index] = {"id": entity_id, "reason": "Cala request failed"}

        await asyncio.gather(*(load(index, entity_id) for index, entity_id in enumerate(body.entity_ids)))
        entries = [entry for entry in entries_by_index if entry is not None]
        omitted = [row for row in omitted_by_index if row is not None]
        if not entries:
            status = 404 if failure_codes and all(code == 404 for code in failure_codes) else (
                503 if 503 in failure_codes else 504 if 504 in failure_codes else 502)
            message = {404: "No favorites were found in the catalog or Cala.",
                       503: "Cala's daily call cap was reached.", 504: "Cala did not answer in time.",
                       502: "Cala request failed for all favorites."}[status]
            raise HTTPException(status, message)
        plan_semaphore = asyncio.Semaphore(3)

        async def plan(entry):
            async with plan_semaphore:
                entry["plan"] = await action_plan(llm, entry["detail"], profile)

        await asyncio.gather(*(plan(entry) for entry in entries))
        pdf = await asyncio.to_thread(render_pdf, entries, omitted, current_mode, datetime.now(timezone.utc))
        headers = {"Content-Disposition": 'attachment; filename="cala-match-favorites.pdf"'}
        if omitted:
            headers["X-Favorites-Not-Included"] = ",".join(row["id"] for row in omitted)
        return Response(content=pdf, media_type="application/pdf", headers=headers)

    try:
        return await asyncio.wait_for(create_report(), timeout=90)
    except asyncio.TimeoutError as exc:
        raise HTTPException(504, "The report took too long.") from exc


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
