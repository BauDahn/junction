from copy import deepcopy
from uuid import uuid4

from chat.profile import empty_profile, merge
from chat.store import now_iso

UNDERSTOOD_KEYS = ("sector_focus", "target_stage", "target_round_size", "geography", "seeking")
CONTEXT_SCHEMA = {
    "type": "object",
    "properties": {
        "startup_name": {"type": "string"}, "one_liner": {"type": "string"},
        "sector": {"type": "string"}, "stage": {"type": "string"}, "location": {"type": "string"},
        "ticket": {"type": "string"}, "target_customers": {"type": "string"},
        "raising_amount": {"type": "string"}, "raising_round": {"type": "string"},
        "role": {"type": "string", "enum": ["founder", "investor", "other"]},
        "competitors": {"type": "array", "items": {"type": "string"}},
        "new_facts": {"type": "array", "items": {"type": "string"}},
        "interests": {"type": "object", "properties": {k: {"type": "array", "items": {"type": "string"}} for k in ("sectors", "regions", "stages")}},
        "what_we_understood": {"type": "object", "properties": {k: {"type": "array", "items": {"type": "string"}} for k in UNDERSTOOD_KEYS}},
    },
}


def _items(values):
    if isinstance(values, str): values = [values]
    result, seen = [], set()
    for value in values or []:
        if isinstance(value, str) and value.strip() and value.strip().casefold() not in seen:
            value = value.strip(); seen.add(value.casefold()); result.append(value)
    return result


def understood_from_profile(profile):
    profile = profile or {}
    supplied = profile.get("what_we_understood") or {}
    interests = profile.get("interests") or {}
    raising = profile.get("raising") or {}
    defaults = {
        "sector_focus": [profile.get("sector"), *(interests.get("sectors") or [])],
        "target_stage": [profile.get("stage"), *(interests.get("stages") or [])],
        "target_round_size": [profile.get("ticket"), raising.get("amount"), raising.get("round")],
        "geography": [profile.get("location"), *(interests.get("regions") or [])],
        "seeking": profile.get("seeking") or [],
    }
    return {key: _items(supplied[key] if key in supplied else defaults[key]) for key in UNDERSTOOD_KEYS}


def update_profile(profile, extracted, source):
    profile = deepcopy(profile or empty_profile())
    patch = dict(extracted or {})
    interests = patch.get("interests") or {}
    patch["interests"] = {key: _items(interests.get(key)) for key in ("sectors", "regions", "stages")}
    updated, _ = merge(profile, patch)
    ticket = next(iter(_items([patch.get("ticket"), patch.get("raising_amount"), *((patch.get("what_we_understood") or {}).get("target_round_size") or [])])), None)
    if ticket: updated["ticket"] = ticket
    existing = understood_from_profile(profile)
    incoming = patch.get("what_we_understood") or {}
    fallback = {
        "sector_focus": [patch.get("sector")], "target_stage": [patch.get("stage")],
        "target_round_size": [ticket], "geography": [patch.get("location")],
        "seeking": [*(patch.get("seeking") or []), *((incoming.get("seeking") or []))],
    }
    understood = {key: _items([*existing[key], *(incoming.get(key) or []), *fallback[key]]) for key in UNDERSTOOD_KEYS}
    updated["what_we_understood"] = understood
    updated["seeking"] = understood["seeking"]
    sources = list(updated.get("context_sources") or [])
    source.setdefault("id", uuid4().hex)
    source.setdefault("created_at", now_iso())
    source["status"] = "ready"
    sources.append(source)
    updated["context_sources"] = sources
    updated["updated_at"] = now_iso()
    return updated, source


def build_context_payload(session_id, profile, source=None):
    profile = deepcopy(profile or empty_profile())
    understood = understood_from_profile(profile)
    profile["what_we_understood"] = understood
    profile["seeking"] = understood["seeking"]
    signals = sum(bool(understood[key]) for key in UNDERSTOOD_KEYS) + bool(profile.get("one_liner"))
    labels = ("Needs Context", "Calibrating", "Good Calibration", "High Signal")
    label = labels[0] if signals <= 2 else labels[1] if signals <= 4 else labels[2] if signals == 5 else labels[3]
    payload = {"session_id": session_id, "profile": profile, "what_we_understood": understood,
               "sources": profile.get("context_sources", []),
               "context_strength": {"score": round(signals / 6 * 100), "signals_added": signals, "signals_total": 6, "label": label}}
    if source is not None: payload["source"] = source
    return payload


async def extract_context(llm, text, images=None):
    system = "Extract only user-provided startup or investor context. Do not verify claims against external sources. Use empty strings and arrays when unknown."
    prompt = f"Extract profile context from this content:\n{text}"
    if images is not None:
        try:
            return await llm.complete_json(system, prompt, CONTEXT_SCHEMA, images=images)
        except (TypeError, RuntimeError) as exc:
            if isinstance(exc, TypeError) or "admite texto" in str(exc).lower():
                return await llm.complete_json(system, prompt, CONTEXT_SCHEMA)
            raise
    return await llm.complete_json(system, prompt, CONTEXT_SCHEMA)
