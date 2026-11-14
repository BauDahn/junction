import re
import unicodedata


def norm_name(s):
    return " ".join(unicodedata.normalize("NFD", s).encode("ascii", "ignore").decode().casefold().split())


async def resolve_entities(intent, client):
    resolved = []
    for entity in intent.get("entities", []):
        raw = await client.entities(entity["name"], entity["type"])
        candidates = raw if isinstance(raw, list) else raw.get("entities", raw.get("results", []))
        candidates = sorted(candidates, key=lambda c: str(c.get("id", "")))
        q = norm_name(entity["name"])
        chosen = next((c for c in candidates if norm_name(c.get("name", "")) == q or any(norm_name(a) == q for a in c.get("aliases", []))), candidates[0] if candidates else None)
        resolved.append({"query": entity, "chosen": chosen, "alternatives": [c for c in candidates if c is not chosen]})
    return resolved
