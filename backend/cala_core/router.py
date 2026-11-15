import json
import hashlib
from pathlib import Path
from canonizador.intent import SECTORS


SCHEMA = {
    "type": "object", "additionalProperties": False, "required": ["parts"],
    "properties": {"parts": {"type": "array", "items": {
        "type": "object", "additionalProperties": False,
        "required": ["type", "text", "claim", "subject", "attribute", "user_value", "profile_patch", "canonical_question_en", "has_entity"],
        "properties": {
            "type": {"type": "string", "enum": ["query", "claim", "profile", "chitchat"]},
            "text": {"type": "string"}, "claim": {"type": ["string", "null"]},
            "subject": {"type": ["string", "null"]}, "attribute": {"type": ["string", "null"]},
            "user_value": {"type": ["string", "number", "null"]},
            "canonical_question_en": {"type": ["string", "null"]}, "has_entity": {"type": "boolean"},
            "profile_patch": {"type": "object", "additionalProperties": False,
                "properties": {
                    "startup_name": {"type": "string"}, "one_liner": {"type": "string"},
                    "sector": {"type": "string"}, "stage": {"type": "string"}, "location": {"type": "string"},
                    "raising_amount": {"type": "string"}, "raising_round": {"type": "string"},
                    "competitors": {"type": "array", "items": {"type": "string"}},
                    "target_customers": {"type": "string"}, "new_facts": {"type": "array", "items": {"type": "string"}},
                    "role": {"type": "string", "enum": ["founder", "investor", "other"]},
                    "interests": {"type": "object", "additionalProperties": False,
                        "properties": {"sectors": {"type": "array", "items": {"type": "string", "enum": SECTORS}},
                            "regions": {"type": "array", "items": {"type": "string"}},
                            "stages": {"type": "array", "items": {"type": "string"}},
                            "follows": {"type": "object", "additionalProperties": False,
                                "properties": {"companies": {"type": "array", "items": {"type": "string"}},
                                    "investors": {"type": "array", "items": {"type": "string"}}}}}}
                }}
        }}}}}

SYSTEM = f"""Split the message into parts, preserving order. Classify each as query, claim, profile or chitchat. Query includes any request for information, data, or statistics, including messages that start with 'queremos ver/saber', 'me gustaría saber', 'cuánto/cuántos'. A message may contain multiple query parts. Claim is an external fact asserted by the user; copy it verbatim into claim, with its subject, attribute, and value. Profile applies only when the user describes their own startup, role, or preferences. Extract only explicit information.
For each query and claim, fill canonical_question_en with a self-contained, neutral, normalized English question, without pleasantries and using standard terms (for example, seed round, venture capital, and country names in English). Equivalent phrasings must produce exactly the same string. Set has_entity to true only when a specific company, person, investor, or event is named; set it to false for statistics or lists without a specific entity.
A message containing profile information returns exactly ONE profile part with all fields together. Preserve every claim and name exactly as written, even if it seems uncertain or mistranscribed; do not discard uncertain data or replace names. Use names verbatim in startup_name, competitors, and follows. If a description identifies the product, sector, location, or funding stage, save it in the corresponding fields and retain additional details in one_liner/new_facts when applicable. Example: 'Somos Saiflow, software para hoteles en Barcelona' preserves startup_name=Saiflow, sector=hotel technology, location=Barcelona, and a one_liner describing the hotel software.
Example: 'Somos Stayflow en Barcelona; nos interesan las fintech nórdicas' → one profile part, profile_patch with startup_name=Stayflow, location=Barcelona, interests.sectors=[fintech], interests.regions=[Nordics].
Literal example: 'Somos Stayflow en Barcelona; nos interesan las fintech nórdicas en etapa seed y quiero saber quién invirtió en Wolt.' → one profile part with profile_patch={{startup_name: 'Stayflow', location: 'Barcelona', interests: {{sectors: ['fintech'], regions: ['Nordics'], stages: ['SEED']}}}} and one query part with canonical_question_en='Who invested in Wolt?' and has_entity=true. Do not omit location, sector, region, or stage when mentioned.
Mixed example: 'somos Stayflow en Barcelona y quiero saber quién invirtió en Mews' produces a profile with startup_name Stayflow/location Barcelona and any stated interests, plus a query about Mews investors.
Normalize interests.sectors to one of these values: {', '.join(SECTORS)}. Use canonical English region names (Nordics, Spain, Finland). Use Cala stage codes such as SEED, SERIES_A, SERIES_B. In profile_patch, include only explicit data; omit unknown or empty fields. For non-profile fields, use null/false according to the schema. If the message is split into multiple profile parts, do not discard data: each part must contain its corresponding explicit attributes."""


async def route(text, profile, llm, cache_dir=None):
    normalized = " ".join((text or "").casefold().split())
    relevant_profile = profile or {}
    key_data = json.dumps({"message": normalized, "profile": relevant_profile}, ensure_ascii=False,
                          sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(key_data.encode()).hexdigest()
    cache_path = Path(cache_dir or "cache") / "router" / f"{digest}.json"
    if cache_path.exists():
        result = json.loads(cache_path.read_text())
    else:
        user = json.dumps({"message": text, "current_profile": relevant_profile}, ensure_ascii=False,
                          sort_keys=True, separators=(",", ":"))
        result = await llm.complete_json(SYSTEM, user, SCHEMA)
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(json.dumps(result, ensure_ascii=False))
    parts = result.get("parts", []) if isinstance(result, dict) else []
    return [p for p in parts if isinstance(p, dict) and p.get("type") in {"query", "claim", "profile", "chitchat"}]
