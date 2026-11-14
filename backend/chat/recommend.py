import asyncio
import hashlib
import json
import re
from . import store


def fingerprint(profile):
    raising = profile.get("raising") or {}
    data = [profile.get(k, "") for k in ("sector", "location", "stage", "one_liner", "target_customers")]
    data += [sorted(str(x).casefold().strip() for x in profile.get("competitors", [])), str(raising.get("round", ""))]
    canonical = json.dumps(data, ensure_ascii=False, separators=(",", ":")).casefold()
    return hashlib.sha256(canonical.encode()).hexdigest()


COUNTRIES = {"madrid":"Spain", "barcelona":"Spain", "valencia":"Spain", "sevilla":"Spain", "bilbao":"Spain", "lisbon":"Portugal", "porto":"Portugal", "paris":"France", "berlin":"Germany", "munich":"Germany", "amsterdam":"Netherlands", "helsinki":"Finland", "stockholm":"Sweden", "oslo":"Norway", "copenhagen":"Denmark", "london":"United Kingdom", "dublin":"Ireland", "tallinn":"Estonia", "zurich":"Switzerland", "vienna":"Austria", "rome":"Italy", "milan":"Italy", "warsaw":"Poland", "prague":"Czechia", "athens":"Greece"}


def _region(location):
    location = " ".join((location or "").split())
    if not location:
        return "Europe"
    key = location.casefold().split(",")[0].strip()
    return COUNTRIES.get(key, location)


def queries(profile):
    sector = " ".join((profile.get("sector") or "startups").split()).casefold()
    stage = " ".join((profile.get("stage") or "early-stage").split()).casefold()
    region = _region(profile.get("location"))
    competitors = profile.get("competitors") or []
    investor = f"Which venture capital investors led or joined {stage} funding rounds of {sector} startups in {region} in the last 24 months? List investor, startup, round and date."
    competitor = f"Which {sector} startups in {region} raised funding in the last 18 months? Include amount, round, date and lead investors."
    if competitors:
        competitor += " Include: " + ", ".join(" ".join(str(c).split()) for c in competitors) + "."
    offering = " ".join((profile.get("one_liner") or profile.get("sector") or "startups").split()).casefold()
    customers = " ".join((profile.get("target_customers") or "businesses").split()).casefold()
    prospect = f"Which companies in {region} are likely customers for {offering} aimed at {customers}? List company, why, and size."
    return {"investors": investor, "competitors": competitor, "prospects": prospect}


SCHEMA = {"type":"object", "properties":{"cards":{"type":"array", "items":{"type":"object", "properties":{"type":{"type":"string"},"title":{"type":"string"},"subtitle":{"type":"string"},"reason":{"type":"string"},"source_ids":{"type":"array","items":{"type":"integer"}}}}}}}


KIND_RULES = {
    "investors": "Each card is ONE investor (a VC fund, angel or corporate investor). title = the investor's name, never a startup. "
                 "subtitle = what they backed (startup, round, amount, date). reason = why this investor fits the founder's startup.",
    "competitors": "Each card is ONE startup or company that competes with the founder's startup (similar product for similar customers). "
                   "title = that company's name. Never an investor, never a customer of a competitor. subtitle = latest funding (amount, round, date, lead). "
                   "reason = why it competes and what its funding signals.",
    "prospects": "Each card is ONE organization that could BUY the founder's product. title = its name. Never a software vendor or a competitor. "
                 "subtitle = what it is (type, size, city). reason = why it would need the product.",
}


def _excluded(kind, profile):
    names = [profile.get("startup_name")]
    if kind != "competitors":
        names += profile.get("competitors") or []
    return [str(n).casefold() for n in names if n]


async def _cards(kind, result, llm, profile):
    if isinstance(profile, str):  # compatibilidad: nombre de la startup
        profile = {"startup_name": profile}
    sources = result.get("sources") or []
    source_text = "\n".join(f"{i}. {json.dumps(s, ensure_ascii=False)}" for i, s in enumerate(sources, 1))
    founder = {k: profile.get(k) for k in ("startup_name", "one_liner", "sector", "location", "target_customers")}
    prompt = json.dumps({"answer": result.get("answer", ""), "sources": source_text, "card_type": kind,
                         "founder_startup": founder, "exclude_names": _excluded(kind, profile)}, ensure_ascii=False)
    system = ("Turn a research answer into up to five cards for a startup founder. " + KIND_RULES[kind] + " "
              "Use only facts stated in the answer; skip entities that do not match the card type. "
              "Write subtitle and reason for the founder, as plain statements (never 'the answer says' or 'the text'), "
              "in the same language as founder_startup.one_liner. Never include names listed in exclude_names. "
              "Cite source_ids from the numbered source list (1-based) that support each card.")
    response = await llm.complete_json(system, prompt, SCHEMA)
    output, dropped = [], 0
    for card in (response.get("cards") or [])[:5]:
        ids = []
        for value in card.get("source_ids", []):
            try:
                index = int(value) - 1
                if 0 <= index < len(sources) and index not in ids:
                    ids.append(index)
            except (ValueError, TypeError):
                pass
        if not ids:
            dropped += 1
            continue
        title = str(card.get("title", "")).casefold()
        if any(name in title for name in _excluded(kind, profile)):
            continue
        output.append({"type":kind[:-1] if kind != "prospects" else "prospect", "title":str(card.get("title", "")), "subtitle":str(card.get("subtitle", "")), "reason":str(card.get("reason", "")), "sources":[sources[i] for i in ids]})
    return output, dropped


async def run_recommendations(session_id, profile, llm, cala):
    fp = fingerprint(profile)
    try:
        store.save_recommendations(session_id, "running", {}, fp)
        qs = queries(profile)
        results = await asyncio.gather(*(cala.search(q) for q in qs.values()), return_exceptions=True)
        categories = {}
        dropped = 0
        failures = 0
        kinds = list(qs)
        ok = [(k, r) for k, r in zip(kinds, results) if not isinstance(r, BaseException)]
        failures = len(kinds) - len(ok)
        categories = {k: [] for k in kinds}
        made = await asyncio.gather(*(_cards(k, r, llm, profile) for k, r in ok), return_exceptions=True)
        for (kind, _), outcome in zip(ok, made):
            if isinstance(outcome, BaseException):
                failures += 1
                continue
            categories[kind], count = outcome
            dropped += count
        status = "error" if failures == 3 else "ready"
        data = {"updated_at":store.now_iso(), **categories, "queries":qs, "dropped_cards":dropped}
        store.save_recommendations(session_id, status, data, fp, data["updated_at"])
        return data
    except Exception as exc:
        data = {"error": str(exc)[:200]}
        store.save_recommendations(session_id, "error", data, fp)
        return data
