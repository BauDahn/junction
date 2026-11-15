from canonizador.api import answer
from canonizador.client import CalaClient


def _sources(data):
    found, seen = [], set()
    def walk(value):
        if isinstance(value, dict):
            for context in value.get("context", []) or []:
                if not isinstance(context, dict):
                    continue
                for origin in context.get("origins", []) or []:
                    if not isinstance(origin, dict):
                        continue
                    document = origin.get("document") or {}
                    source = origin.get("source") or {}
                    if isinstance(document, str): document = {"name": document}
                    if isinstance(source, str): source = {"name": source}
                    if not isinstance(document, dict): document = {}
                    if not isinstance(source, dict): source = {}
                    name = document.get("name") or source.get("name")
                    url = document.get("url") or source.get("url")
                    if name:
                        key = ("url", url) if url else ("name", name)
                        if key not in seen:
                            seen.add(key)
                            normalized = {"name": name}
                            if url: normalized["url"] = url
                            found.append(normalized)
            for source in value.get("sources", []) or []:
                if isinstance(source, dict):
                    document = source.get("document")
                    document_obj = document if isinstance(document, dict) else {}
                    name = source.get("name") or document_obj.get("name") or (document if isinstance(document, str) else None)
                    url = document_obj.get("url") or (document if isinstance(document, str) and document.startswith("http") else None) or source.get("url")
                    if not name:
                        continue
                    normalized = {"name": name}
                    if url: normalized["url"] = url
                    if source.get("date"): normalized["date"] = source["date"]
                    rank = source.get("source_rank") or source.get("rank")
                    if rank: normalized["source_rank"] = rank
                    key = ("url", normalized["url"]) if normalized.get("url") else ("name", normalized["name"])
                    if key not in seen:
                        seen.add(key)
                        found.append(normalized)
            for child in value.values(): walk(child)
        elif isinstance(value, list):
            for child in value: walk(child)
    walk(data)
    return found[:12]


def _call(tool, query):
    return {"tool": tool, "query": str(query or "")}


def _title(part, intent):
    entities = intent.get("entities") or []
    subject = entities[0].get("name") if entities and isinstance(entities[0], dict) else None
    attribute = intent.get("attribute") or "other"
    labels = {"funding_round": "funding round", "total_funding": "total funding", "investors": "investors",
              "lead_investors": "lead investors", "founders": "founders", "executives": "executives",
              "headcount": "team size", "acquisitions": "acquisitions", "company_list": "startups"}
    if attribute == "funding_round":
        label = "funding round"
        round_label = (intent.get("filters") or {}).get("round_label")
        if round_label:
            label += " " + str(round_label).replace("_", " ").title()
    else:
        label = labels.get(attribute, "data")
    if attribute == "company_list":
        filters = intent.get("filters") or {}
        pieces = ["Startups"]
        if filters.get("sector"): pieces.append(str(filters["sector"]).title())
        if filters.get("location"): pieces.append(str(filters["location"]))
        return " · ".join(pieces)
    return f"{subject} · {label}" if subject else label.title()


def _normalize_block_sources(block):
    if isinstance(block, dict):
        if isinstance(block.get("sources"), list):
            block["sources"] = _sources({"sources": block["sources"]})
        for child in block.values(): _normalize_block_sources(child)
    elif isinstance(block, list):
        for child in block: _normalize_block_sources(child)
    return block


def _table_from_entity(data, call):
    rows, sources = [], _sources(data)
    def visit(node, prefix=""):
        if isinstance(node, dict):
            props = node.get("properties")
            if isinstance(props, dict):
                for key, val in props.items():
                    if isinstance(val, dict) and "value" in val:
                        rows.append([key, val.get("value"), "; ".join(s.get("name", s.get("url", "")) for s in val.get("sources", []) if isinstance(s, dict)), val.get("date"), val.get("source_rank")])
                    elif not isinstance(val, (dict, list)):
                        rows.append([key, val, "", None, None])
            for k, v in node.items():
                if k != "properties": visit(v, prefix)
        elif isinstance(node, list):
            for item in node: visit(item, prefix)
    visit(data)
    if not rows: return None
    return {"type": "cala_table", "title": "Cala data", "call": call,
            "columns": ["field", "value", "source", "date", "source_rank"], "rows": rows, "sources": sources}


async def _safe(call, default):
    """Un paso de respaldo que falla (422, 429, red) no rompe el chat: se pasa al siguiente."""
    try:
        return await call
    except Exception:
        return default


async def _safe_call(method, *args, default=None, **kwargs):
    try:
        return await method(*args, **kwargs)
    except Exception:
        return default


async def _execute(part, *, cala=None, llm=None, cache_dir=None):
    legacy_input = not isinstance(part, dict)
    if isinstance(part, dict):
        text = part.get("text", "")
        canonical = part.get("canonical_question_en") or text
        has_entity = bool(part.get("has_entity"))
    else:  # Compatibility for internal callers during rollout.
        text = canonical = str(part or "")
        has_entity = True
    client = cala or CalaClient(cache_dir=cache_dir or "cache")
    if not has_entity:
        return await _search_block(client, canonical, text)

    canonizer_error = None
    try:
        result = await answer(canonical, llm=llm, client=client, cache_dir=cache_dir)
        if not isinstance(result, dict):
            result = {}
        elif not isinstance(result.get("result"), list) and not ((result.get("result") or {}).get("rows") or (result.get("result") or {}).get("properties")):
            canonizer_error = "NoUsefulData"
    except Exception as exc:
        # No exception details or user data in the public diagnostics.
        result = {}
        canonizer_error = type(exc).__name__
    data = result.get("result") or {}
    intent = result.get("intent") or {}
    intent_entities = intent.get("entities") or []
    filters = intent.get("filters") or {}
    list_filter = any(filters.get(k) not in (None, "", [], {}) for k in ("location", "sector", "min_funding", "round_label", "year"))
    should_search = canonizer_error is None and not legacy_input and (not intent_entities or (intent.get("attribute") == "other" and not list_filter))
    if should_search:
        tried = ([{"tool": "canonizer", "error": canonizer_error}] if canonizer_error else [])
        return await _search_block(client, canonical, text, title=_title({"text": text}, intent), tried=tried)
    if isinstance(data, list):
        # Camino de entidades del canonizador: lista de retrieve/search, no filas de knowledge_query.
        ids = ",".join(result.get("entity_ids") or []) or text
        table = _table_from_entity(data, _call("entity", f"retrieve:{ids}"))
        if table:
            table["title"] = _title({"text": text}, result.get("intent") or {})
            return _normalize_block_sources(table)
        data = {}
    query = data.get("query", text)
    tried = ([{"tool": "canonizer", "error": canonizer_error}] if canonizer_error else []) + [_call("knowledge_query", query)]
    rows = data.get("rows") or []
    title = _title({"text": text}, result.get("intent") or {})
    if rows:
        columns = list(rows[0].keys()) if isinstance(rows[0], dict) else []
        values = [[row.get(c) for c in columns] for row in rows] if columns else rows
        return _normalize_block_sources({"type": "cala_table", "title": title, "call": tried[0], "columns": columns,
                "rows": values, "sources": data.get("sources") or _sources(rows)})

    closest = None
    subject = ((intent.get("entities") or [{}])[0].get("name") if isinstance(intent.get("entities"), list) else None)
    subject = subject or text
    if client is not None and len(subject.split()) <= 6 and len(subject) <= 60:
        tried.append(_call("entity", subject))
        entity_type = "COMPANY"
        entities = intent.get("entities") or []
        if entities and isinstance(entities[0], dict): entity_type = entities[0].get("type") or entity_type
        found = await _safe_call(client.entities, subject, entity_type, default=[])
        candidates = found if isinstance(found, list) else found.get("entities", []) if isinstance(found, dict) else []
        if candidates:
            entity = next((x for x in candidates if str(x.get("name", "")).casefold() == subject.casefold()), candidates[0])
            entity_id = entity.get("id")
            if entity_id:
                tried.append(_call("entity", f"introspection:{entity_id}"))
                intro = await _safe_call(client.introspection, entity_id, default={})
                props = intro.get("properties", [])
                rels = intro.get("relationships", {})
                requested_rels = {d: {name: {"limit": 100} for name in names} for d, names in rels.items() if names}
                tried.append(_call("entity", f"retrieve:{entity_id} properties={props} relationships={requested_rels}"))
                retrieved = await _safe_call(client.retrieve, entity_id, properties=props, relationships=requested_rels, default={})
                closest = _table_from_entity(retrieved, tried[-1])
                if closest:
                    closest["title"] = title
                    return _normalize_block_sources(closest)
    attribute = str(intent.get("attribute") or "company facts").replace("_", " ")
    search_query = canonical
    tried.append(_call("knowledge_search", search_query))
    if client is not None:
        searched = await _safe_call(client.search, search_query, default={})
        markdown = searched.get("answer") or searched.get("markdown") or searched.get("content") or "" if isinstance(searched, dict) else ""
        if markdown:
            return _normalize_block_sources({"type": "cala_answer", "title": canonical[:80], "call": tried[-1], "markdown": markdown,
                    "sources": _sources(searched)})
    return _normalize_block_sources({"type": "not_found", "title": title, "tried": tried, **({"closest": closest} if closest else {})})


async def execute(part, *, cala=None, llm=None, cache_dir=None):
    """Public executor boundary: chat blocks must survive any upstream failure."""
    try:
        return await _execute(part, cala=cala, llm=llm, cache_dir=cache_dir)
    except Exception as exc:
        text = part.get("text", "") if isinstance(part, dict) else str(part or "")
        return {"type": "not_found", "title": text[:80] or "Data", "tried": [
            {"tool": "executor", "error": type(exc).__name__}]}


async def _search_block(client, canonical, text, *, title="Data", tried=None, closest=None):
    tried = list(tried or [])
    tried.append(_call("knowledge_search", canonical))
    searched = await _safe_call(client.search, canonical, default={}) if client is not None else {}
    markdown = (searched.get("answer") or searched.get("markdown") or searched.get("content") or "") if isinstance(searched, dict) else ""
    if markdown:
        return _normalize_block_sources({"type": "cala_answer", "title": canonical[:80], "call": tried[-1], "markdown": markdown, "sources": _sources(searched)})
    return _normalize_block_sources({"type": "not_found", "title": title, "tried": tried, **({"closest": closest} if closest else {})})
