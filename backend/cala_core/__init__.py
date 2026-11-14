import asyncio

from .claims import check
from .executor import execute
from .executor import _normalize_block_sources
from .router import route


SECTOR_ALIASES = {
    "hotel tech": "hotel technology", "hotel technology": "hotel technology", "tecnologia hotelera": "hotel technology",
    "fintech": "fintech", "tecnologia financiera": "fintech", "health tech": "healthtech", "healthtech": "healthtech",
    "climate tech": "climate tech", "tecnologia climatica": "climate tech", "saas": "saas", "ai": "ai", "ia": "ai",
    "cybersecurity": "cybersecurity", "ciberseguridad": "cybersecurity", "edtech": "edtech", "proptech": "proptech",
    "mobility": "mobility", "movilidad": "mobility", "foodtech": "foodtech", "biotech": "biotech",
    "ecommerce": "ecommerce", "comercio electronico": "ecommerce", "logistics": "logistics", "logistica": "logistics",
    "gaming": "gaming", "videojuegos": "gaming", "other": "other", "otro": "other",
}
REGION_ALIASES = {"nordic countries": "Nordics", "nordic": "Nordics", "nórdicas": "Nordics", "nordicas": "Nordics",
                  "países nórdicos": "Nordics", "paises nordicos": "Nordics", "norte de europa": "Nordics",
                  "españa": "Spain", "espana": "Spain", "finlandia": "Finland", "suecia": "Sweden",
                  "noruega": "Norway", "dinamarca": "Denmark", "alemania": "Germany", "francia": "France",
                  "reino unido": "United Kingdom", "estados unidos": "United States"}
STAGE_ALIASES = {"pre-seed": "PRE_SEED", "pre seed": "PRE_SEED", "seed": "SEED", "serie a": "SERIES_A",
                 "series a": "SERIES_A", "serie b": "SERIES_B", "series b": "SERIES_B", "serie c": "SERIES_C",
                 "series c": "SERIES_C", "serie d": "SERIES_D", "series d": "SERIES_D", "serie e": "SERIES_E",
                 "series e": "SERIES_E", "growth": "GROWTH", "late stage": "LATE_STAGE"}


def _normalize_interests(interests):
    if not isinstance(interests, dict): return {}
    result = {}
    for key in ("sectors", "regions", "stages"):
        values = interests.get(key) or []
        if isinstance(values, str): values = [values]
        normalized = []
        for value in values:
            if not isinstance(value, str) or not value.strip(): continue
            raw = value.strip()
            folded = raw.casefold()
            if key == "sectors":
                value = SECTOR_ALIASES.get(folded, "other")
            elif key == "regions":
                value = REGION_ALIASES.get(folded, raw.title())
            else:
                value = STAGE_ALIASES.get(folded, raw.upper().replace(" ", "_"))
            if value not in normalized: normalized.append(value)
        if normalized: result[key] = normalized
    follows = interests.get("follows") or {}
    if isinstance(follows, dict):
        clean_follows = {k: list(dict.fromkeys(x.strip() for x in (follows.get(k) or []) if isinstance(x, str) and x.strip()))
                         for k in ("companies", "investors")}
        clean_follows = {k: v for k, v in clean_follows.items() if v}
        if clean_follows: result["follows"] = clean_follows
    return result


def _clean(value):
    if isinstance(value, dict):
        return {k: cleaned for k, v in value.items() if (cleaned := _clean(v)) not in (None, "", [], {})}
    if isinstance(value, list):
        return [cleaned for v in value if (cleaned := _clean(v)) not in (None, "", [], {})]
    if isinstance(value, str): return value.strip()
    return value


def _profile_patch(patch):
    patch = dict(patch or {})
    if "interests" in patch:
        patch["interests"] = _normalize_interests(patch["interests"])
    return _clean(patch)


def _merge_patch(target, patch):
    for key, value in (patch or {}).items():
        if key == "interests" and isinstance(value, dict):
            old = target.setdefault("interests", {"sectors": [], "regions": [], "stages": [], "follows": {"companies": [], "investors": []}})
            for sub, item in value.items():
                if sub == "follows" and isinstance(item, dict):
                    follows = old.setdefault("follows", {})
                    for kind, names in item.items():
                        current = follows.setdefault(kind, [])
                        current.extend(x for x in names or [] if x not in current)
                elif isinstance(item, list):
                    current = old.setdefault(sub, [])
                    current.extend(x for x in item if x not in current)
        elif isinstance(value, list):
            current = target.setdefault(key, [])
            current.extend(x for x in value if x not in current)
        elif value not in (None, ""):
            target[key] = value


async def handle_message(text, profile, llm, cala=None, cache_dir=None):
    parts = await route(text, profile, llm)
    profile_patch = {}

    async def process(part):
        kind = part["type"]
        if kind == "profile":
            patch = _profile_patch(part.get("profile_patch"))
            _merge_patch(profile_patch, patch)
            return {"type": "profile_update", "changes": patch} if patch else None
        if kind == "chitchat":
            return {"type": "text", "text": part.get("text", "¡De acuerdo!")}
        evidence = await execute(part.get("text", text), cala=cala, llm=llm, cache_dir=cache_dir)
        if kind == "claim":
            return await check(part, evidence, llm)
        return evidence

    results = await asyncio.gather(*(process(part) for part in parts))
    return {"blocks": [_normalize_block_sources(block) for block in results if block], "profile_patch": _clean(profile_patch)}
