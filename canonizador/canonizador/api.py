import json
import os
from pathlib import Path

from .cache import DiskCache
from .client import CalaClient
from .intent import IntentParser
from .normalize import normalize
from .plan import build_plan
from .resolve import resolve_entities

ROUND_REL = "PARTICIPATES_IN_FUNDING_ROUND"
ROUND_PROPERTIES = ["name", "round_label", "instrument", "transaction_value", "transaction_value_units", "announcement_date", "event_date"]


def _value(properties, key):
    item = properties.get(key)
    return item.get("value") if isinstance(item, dict) and "value" in item else item


def _sources(*objects):
    found = {}
    def walk(value):
        if isinstance(value, dict):
            for source in value.get("sources", []) or []:
                if isinstance(source, dict):
                    identity = json.dumps(source, sort_keys=True, ensure_ascii=False)
                    found[identity] = source
            for child in value.values(): walk(child)
        elif isinstance(value, list):
            for child in value: walk(child)
    for obj in objects: walk(obj)
    return [found[k] for k in sorted(found)]


async def answer_intent(intent, client):
    """Ejecuta una intención ya estructurada, sin invocar el proveedor LLM."""
    if intent.get("attribute") not in ("funding_round", "lead_investors"):
        raise NotImplementedError("answer_intent implementa actualmente consultas de rondas")
    if not intent.get("entities"):
        return {"company": None, "rounds": []}
    entity = intent["entities"][0]
    search = await client.entities(entity["name"], entity["type"])
    candidates = search if isinstance(search, list) else search.get("entities", [])
    candidates = sorted(candidates, key=lambda x: str(x.get("id", "")))
    exact = next((c for c in candidates if c.get("name", "").casefold() == entity["name"].casefold()), None)
    company = exact or (candidates[0] if candidates else None)
    if not company:
        return {"company": None, "rounds": []}

    company_id = company["id"]
    company_intro = await client.introspection(company_id)
    available_rel = company_intro.get("relationships", {}).get("outgoing", [])
    rels = {"outgoing": {ROUND_REL: {"limit": 100}}} if ROUND_REL in available_rel else {}
    company_data = await client.retrieve(company_id, properties=[p for p in ["name"] if p in company_intro.get("properties", [])], relationships=rels)
    linked = company_data.get("relationships", {}).get("outgoing", {}).get(ROUND_REL, [])
    filters = intent.get("filters", {})
    wanted_label = str(filters.get("round_label") or "").upper().replace(" ", "_")
    wanted_year = str(filters.get("year") or "")
    rounds = []
    for link in sorted(linked, key=lambda x: (x.get("name", "").casefold(), str(x.get("id", "")))):
        link_props = link.get("properties", {})
        role = link_props.get("role")
        if isinstance(role, dict): role = role.get("value")
        if role != "ISSUER": continue
        rid = link.get("id")
        intro = await client.introspection(rid)
        available_props = intro.get("properties", [])
        available_incoming = intro.get("relationships", {}).get("incoming", [])
        incoming = {"incoming": {ROUND_REL: {"limit": 100}}} if ROUND_REL in available_incoming else {}
        requested = [p for p in ROUND_PROPERTIES if p in available_props]
        data = await client.retrieve(rid, properties=requested, relationships=incoming)
        rp = data.get("properties", {})
        name = _value(rp, "name") or link.get("name")
        label = _value(rp, "round_label")
        date = _value(rp, "announcement_date") or _value(rp, "event_date")
        date_text = str(date or "")
        if wanted_label and wanted_label not in str(label or name or "").upper().replace(" ", "_"):
            continue
        if wanted_year and wanted_year not in date_text:
            continue
        participants = data.get("relationships", {}).get("incoming", {}).get(ROUND_REL, [])
        leads, investors = [], []
        participant_sources = []
        for person in participants:
            pp = person.get("properties", {})
            participant_sources.extend(pp.get("sources", []) if isinstance(pp.get("sources"), list) else [])
            participant_role = pp.get("role")
            if isinstance(participant_role, dict): participant_role = participant_role.get("value")
            if participant_role != "INVESTOR": continue
            lead = pp.get("is_lead", False)
            if isinstance(lead, dict): lead = lead.get("value", False)
            (leads if lead else investors).append(person.get("name", ""))
        amount = _value(rp, "transaction_value")
        currency = _value(rp, "transaction_value_units")
        rounds.append({"name": name, "amount": amount, "currency": currency, "date": date, "lead_investors": sorted(set(filter(None, leads)), key=str.casefold), "investors": sorted(set(filter(None, investors)), key=str.casefold), "sources": _sources(link, data, participant_sources)})
    rounds.sort(key=lambda r: (str(r.get("date") or ""), str(r.get("name") or "").casefold()))
    return {"company": {"id": company_id, "name": company_data.get("name") or company.get("name")}, "rounds": rounds}


def _env():
    path = Path(__file__).resolve().parents[2] / "backend" / ".env"
    if path.exists():
        for line in path.read_text().splitlines():
            if line.startswith("CALA_API_KEY=") and not os.getenv("CALA_API_KEY"):
                os.environ["CALA_API_KEY"] = line.partition("=")[2].strip().strip("\"'")


async def answer(question, *, llm=None, client=None, cache_dir=None):
    _env()
    root = Path(cache_dir or os.getenv("CANONIZADOR_CACHE", Path(__file__).resolve().parents[1] / "cache"))
    cache = DiskCache(root)
    cala = client or CalaClient(cache_dir=root)
    intent = await IntentParser(llm, cache).parse(normalize(question))
    if intent.get("attribute") in ("funding_round", "lead_investors"):
        result = await answer_intent(intent, cala)
        ids = [result["company"]["id"]] if result.get("company") else []
        canonical = {"entity_ids": ids, "attribute": intent["attribute"], "filters": intent.get("filters", {})}
        cached = cache.get("answers", canonical)
        if cached is not None:
            cached["cache_hit"] = True; cached["cala_calls"] = cala.calls
            return cached
        response = {"intent": intent, "entity_ids": ids, "plan": build_plan(intent, ids[0]) if ids else [], "result": result, "cache_hit": False, "cala_calls": cala.calls}
        cache.put("answers", canonical, response)
        return response
    resolved = await resolve_entities(intent, cala)
    ids = sorted(x["chosen"]["id"] for x in resolved if x["chosen"] and x["chosen"].get("id"))
    canonical = {"entity_ids": ids, "attribute": intent["attribute"], "filters": intent.get("filters", {})}
    cached = cache.get("answers", canonical)
    if cached is not None:
        cached["cache_hit"] = True; cached["cala_calls"] = cala.calls
        return cached
    plans = [build_plan(intent, item["chosen"]["id"]) for item in resolved if item["chosen"] and item["chosen"].get("id")]
    results = []
    if intent["attribute"] == "other":
        names = ", ".join(e["name"] for e in intent.get("entities", []))
        canonical_q = f"Provide {intent['attribute']} information about {names}".strip()
        results.append(await cala.search(canonical_q))
    else:
        for plan_group in plans:
            for step in plan_group:
                if "entity_id" not in step: continue
                entity_id = step["entity_id"]
                introspection = await cala.introspection(entity_id)
                props = [p for p in step.get("properties", []) if p in introspection.get("properties", [])]
                relations = step.get("relationships", {})
                results.append(await cala.retrieve(entity_id, properties=props, relationships=relations, numerical_observations=step.get("numerical_observations", [])))
    response = {"intent": intent, "entity_ids": ids, "plan": plans, "result": results, "cache_hit": False, "cala_calls": cala.calls}
    cache.put("answers", canonical, response)
    return response
