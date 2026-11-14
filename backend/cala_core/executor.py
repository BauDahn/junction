from canonizador.api import answer
from canonizador.client import CalaClient


def _sources(data):
    found, seen = [], set()
    def walk(value):
        if isinstance(value, dict):
            for source in value.get("sources", []) or []:
                if isinstance(source, dict):
                    name = source.get("name") or source.get("document")
                    url = source.get("document") or source.get("url")
                    if not name:
                        continue
                    normalized = {"name": name}
                    if url: normalized["url"] = url
                    if source.get("date"): normalized["date"] = source["date"]
                    rank = source.get("source_rank") or source.get("rank")
                    if rank: normalized["source_rank"] = rank
                    key = (normalized.get("url"), normalized["name"])
                    if key not in seen:
                        seen.add(key)
                        found.append(normalized)
            for child in value.values(): walk(child)
        elif isinstance(value, list):
            for child in value: walk(child)
    walk(data)
    return found


def _call(tool, query):
    return {"tool": tool, "query": str(query or "")}


def _title(part, intent):
    entities = intent.get("entities") or []
    subject = entities[0].get("name") if entities and isinstance(entities[0], dict) else None
    attribute = intent.get("attribute") or "other"
    labels = {"funding_round": "ronda", "total_funding": "financiación total", "investors": "inversores",
              "lead_investors": "inversores líderes", "founders": "fundadores", "executives": "directivos",
              "headcount": "equipo", "acquisitions": "adquisiciones", "company_list": "startups"}
    if attribute == "funding_round":
        label = "ronda"
        round_label = (intent.get("filters") or {}).get("round_label")
        if round_label:
            label += " " + str(round_label).replace("_", " ").title()
    else:
        label = labels.get(attribute, "datos")
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
    return {"type": "cala_table", "title": "Datos de Cala", "call": call,
            "columns": ["campo", "valor", "fuente", "fecha", "source_rank"], "rows": rows, "sources": sources}


async def execute(text, *, cala=None, llm=None, cache_dir=None):
    result = await answer(text, llm=llm, client=cala, cache_dir=cache_dir)
    data = result.get("result") or {}
    if isinstance(data, list):
        # Camino de entidades del canonizador: lista de retrieve/search, no filas de knowledge_query.
        ids = ",".join(result.get("entity_ids") or []) or text
        table = _table_from_entity(data, _call("entity", f"retrieve:{ids}"))
        if table:
            table["title"] = _title({"text": text}, result.get("intent") or {})
            return _normalize_block_sources(table)
        data = {}
    query = data.get("query", text)
    tried = [_call("knowledge_query", query)]
    rows = data.get("rows") or []
    title = _title({"text": text}, result.get("intent") or {})
    if rows:
        columns = list(rows[0].keys()) if isinstance(rows[0], dict) else []
        values = [[row.get(c) for c in columns] for row in rows] if columns else rows
        return _normalize_block_sources({"type": "cala_table", "title": title, "call": tried[0], "columns": columns,
                "rows": values, "sources": data.get("sources") or _sources(rows)})

    closest = None
    intent = result.get("intent") or {}
    subject = ((intent.get("entities") or [{}])[0].get("name") if isinstance(intent.get("entities"), list) else None)
    subject = subject or text
    client = cala or CalaClient(cache_dir=cache_dir or "cache")
    if client is not None:
        tried.append(_call("entity", subject))
        entity_type = "COMPANY"
        entities = intent.get("entities") or []
        if entities and isinstance(entities[0], dict): entity_type = entities[0].get("type") or entity_type
        found = await client.entities(subject, entity_type)
        candidates = found if isinstance(found, list) else found.get("entities", []) if isinstance(found, dict) else []
        if candidates:
            entity = next((x for x in candidates if str(x.get("name", "")).casefold() == subject.casefold()), candidates[0])
            entity_id = entity.get("id")
            if entity_id:
                tried.append(_call("entity", f"introspection:{entity_id}"))
                intro = await client.introspection(entity_id)
                props = intro.get("properties", [])
                rels = intro.get("relationships", {})
                requested_rels = {d: {name: {"limit": 100} for name in names} for d, names in rels.items() if names}
                tried.append(_call("entity", f"retrieve:{entity_id} properties={props} relationships={requested_rels}"))
                retrieved = await client.retrieve(entity_id, properties=props, relationships=requested_rels)
                closest = _table_from_entity(retrieved, tried[-1])
                if closest:
                    closest["title"] = title
                    return _normalize_block_sources(closest)
    attribute = str(intent.get("attribute") or "company facts").replace("_", " ")
    search_query = f"Find {attribute} for {subject}. Return only sourced Cala data."
    tried.append(_call("knowledge_search", search_query))
    if client is not None:
        searched = await client.search(search_query)
        markdown = searched.get("answer") or searched.get("markdown") or searched.get("content") or "" if isinstance(searched, dict) else ""
        if markdown:
            return _normalize_block_sources({"type": "cala_answer", "title": title, "call": tried[-1], "markdown": markdown,
                    "sources": _sources(searched)})
    return _normalize_block_sources({"type": "not_found", "title": title, "tried": tried, **({"closest": closest} if closest else {})})
