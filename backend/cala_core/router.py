import json
from canonizador.intent import SECTORS


SCHEMA = {
    "type": "object", "additionalProperties": False, "required": ["parts"],
    "properties": {"parts": {"type": "array", "items": {
        "type": "object", "additionalProperties": False,
        "required": ["type", "text", "claim", "subject", "attribute", "user_value", "profile_patch"],
        "properties": {
            "type": {"type": "string", "enum": ["query", "claim", "profile", "chitchat"]},
            "text": {"type": "string"}, "claim": {"type": ["string", "null"]},
            "subject": {"type": ["string", "null"]}, "attribute": {"type": ["string", "null"]},
            "user_value": {"type": ["string", "number", "null"]},
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

SYSTEM = f"""Divide el mensaje en partes, preservando orden. Clasifica cada una como query, claim, profile o chitchat. Query es pregunta sobre Cala; claim es un dato externo afirmado por el usuario y debe copiarse literalmente en claim, con sujeto, atributo y valor; profile contiene datos propios/gustos. Extrae solo lo explícito. Un mensaje puede combinar partes. Ejemplo: 'somos Stayflow en Barcelona y quiero saber quién invirtió en Mews' produce profile con startup_name Stayflow/location Barcelona y query sobre inversores de Mews. Normaliza interests.sectors a uno de estos valores: {', '.join(SECTORS)}. regions en inglés canónico (Nordics, Spain, Finland). stages en códigos de Cala, por ejemplo SEED, SERIES_A, SERIES_B. Completa todos los campos requeridos, usa null/campo vacío cuando no corresponda."""


async def route(text, profile, llm):
    user = json.dumps({"message": text, "current_profile": profile or {}}, ensure_ascii=False)
    result = await llm.complete_json(SYSTEM, user, SCHEMA)
    parts = result.get("parts", []) if isinstance(result, dict) else []
    return [p for p in parts if isinstance(p, dict) and p.get("type") in {"query", "claim", "profile", "chitchat"}]
