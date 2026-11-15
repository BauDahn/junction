import math
import re
from copy import deepcopy
from uuid import uuid4

from chat.profile import empty_profile, merge
from chat.store import now_iso

UNDERSTOOD_KEYS = ("sector_focus", "target_stage", "target_round_size", "geography", "seeking")
_UNIT_MULT = {
    "k": 1e3, "thousand": 1e3,
    "m": 1e6, "mm": 1e6, "million": 1e6,
    "bn": 1e9, "billion": 1e9,
}
_CURRENCY_MAP = {
    "€": "EUR", "EUR": "EUR", "EURO": "EUR", "EUROS": "EUR",
    "$": "USD", "USD": "USD", "DOLLAR": "USD", "DOLLARS": "USD",
    "£": "GBP", "GBP": "GBP", "POUND": "GBP", "POUNDS": "GBP",
}
CONTEXT_SCHEMA = {
    "type": "object",
    "properties": {
        "startup_name": {"type": "string"}, "one_liner": {"type": "string"},
        "sector": {"type": "string"}, "stage": {"type": "string"}, "location": {"type": "string"},
        "ticket": {"type": "string"}, "ticket_min": {"type": "number"}, "ticket_max": {"type": "number"}, "ticket_currency": {"type": "string"},
        "target_customers": {"type": "string"},
        "raising_amount": {"type": "string"}, "raising_round": {"type": "string"},
        "role": {"type": "string", "enum": ["founder", "investor", "other"]},
        "competitors": {"type": "array", "items": {"type": "string"}},
        "new_facts": {"type": "array", "items": {"type": "string"}},
        "interests": {"type": "object", "properties": {k: {"type": "array", "items": {"type": "string"}} for k in ("sectors", "regions", "stages")}},
        "what_we_understood": {"type": "object", "properties": {k: {"type": "array", "items": {"type": "string"}} for k in UNDERSTOOD_KEYS}},
    },
}


def _detect_currency(raw_text, explicit=None):
    if isinstance(explicit, str) and explicit.strip():
        key = explicit.strip().upper()
        for sym, code in (("€", "EUR"), ("$", "USD"), ("£", "GBP")):
            if sym in key:
                return code
        return _CURRENCY_MAP.get(key, key)
    if isinstance(raw_text, str) and raw_text.strip():
        if "€" in raw_text or re.search(r"\b(?:eur|euros?)\b", raw_text, re.I):
            return "EUR"
        if "£" in raw_text or re.search(r"\b(?:gbp|pounds?)\b", raw_text, re.I):
            return "GBP"
        if "$" in raw_text or re.search(r"\b(?:usd|dollars?)\b", raw_text, re.I):
            return "USD"
    return None


def _clean_number(value):
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        num = float(value)
        return num if math.isfinite(num) and num > 0 else None
    return None


def _format_num(value):
    value = round(float(value), 6)
    return int(value) if value.is_integer() else value


def _parse_ticket_range(raw_text, *, ticket_min=None, ticket_max=None, currency=None):
    """Convierte rangos o montos de ticket a unidades base numéricas y moneda."""
    detected_currency = _detect_currency(raw_text, currency)
    explicit = [n for n in (_clean_number(ticket_min), _clean_number(ticket_max)) if n is not None]
    if explicit:
        lo, hi = min(explicit), max(explicit)
        return {"min": _format_num(lo), "max": _format_num(hi), "currency": detected_currency}
    if not isinstance(raw_text, str) or not raw_text.strip():
        return None
    normalized = re.sub(r",(?=\d{3}(?!\d))", "", raw_text)
    normalized = re.sub(r"(\d),(\d{1,2})(?!\d)", r"\1.\2", normalized)
    matches = re.findall(
        r"(?<![A-Za-z])(\d+(?:\.\d+)?)\s*(bn|billion|mm|million|thousand|k|m)?\b",
        normalized,
        re.I,
    )
    if not matches:
        return None
    # Propaga el sufijo desde la derecha cuando un rango solo lo escribe al final (ej. "1-3M EUR").
    resolved = []
    trailing_unit = None
    for raw_num, unit in reversed(matches):
        unit_key = unit.lower() if unit else trailing_unit
        if unit:
            trailing_unit = unit_key
        num = float(raw_num) * _UNIT_MULT.get(unit_key, 1.0)
        if math.isfinite(num) and num > 0:
            resolved.append(num)
    if not resolved:
        return None
    lo, hi = min(resolved), max(resolved)
    return {"min": _format_num(lo), "max": _format_num(hi), "currency": detected_currency}


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
    has_explicit_bounds = _clean_number(patch.get("ticket_min")) is not None or _clean_number(patch.get("ticket_max")) is not None
    raw_ticket = ticket or (None if has_explicit_bounds else (updated.get("ticket") or (updated.get("raising") or {}).get("amount")))
    ticket_range = _parse_ticket_range(
        raw_ticket,
        ticket_min=patch.get("ticket_min"),
        ticket_max=patch.get("ticket_max"),
        currency=patch.get("ticket_currency"),
    )
    if ticket_range: updated["ticket_range"] = ticket_range
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
