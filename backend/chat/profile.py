from copy import deepcopy
from .store import now_iso


def empty_profile():
    return {"competitors": [], "facts": [], "updated_at": now_iso()}


def merge(profile, patch):
    result = deepcopy(profile or empty_profile())
    before = {k: v for k, v in result.items() if k != "updated_at"}
    for key in ("startup_name", "one_liner", "sector", "stage", "location", "target_customers"):
        value = patch.get(key)
        if isinstance(value, str) and value.strip():
            result[key] = value.strip()
    raising = dict(result.get("raising") or {})
    for key, source in (("amount", "raising_amount"), ("round", "raising_round")):
        value = patch.get(source)
        if isinstance(value, str) and value.strip():
            raising[key] = value.strip()
    if raising:
        result["raising"] = raising
    competitors = result.setdefault("competitors", [])
    seen = {item.casefold() for item in competitors}
    for item in patch.get("competitors", []) or []:
        if isinstance(item, str) and item.strip() and item.strip().casefold() not in seen:
            competitors.append(item.strip())
            seen.add(item.strip().casefold())
    facts = result.setdefault("facts", [])
    fact_texts = {f.get("text", "").casefold() for f in facts}
    for text in patch.get("new_facts", []) or []:
        if isinstance(text, str) and text.strip() and text.strip().casefold() not in fact_texts:
            facts.append({"text": text.strip(), "origin": "user"})
            fact_texts.add(text.strip().casefold())
    changed = before != {k: v for k, v in result.items() if k != "updated_at"}
    if changed:
        result["updated_at"] = now_iso()
    return result, changed
