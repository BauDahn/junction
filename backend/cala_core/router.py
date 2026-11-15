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

SYSTEM = f"""Divide el mensaje en partes, preservando orden. Clasifica cada una como query, claim, profile o chitchat. Query es cualquier pedido de información, datos o estadísticas, incluso si empieza con 'queremos ver/saber', 'me gustaría saber', 'cuánto/cuántos'; puede dividirse en varias partes query. Claim es un dato externo afirmado por el usuario y debe copiarse literalmente en claim, con sujeto, atributo y valor. Profile es solo cuando describe su propia startup, rol o gustos. Extrae solo lo explícito.
Para cada query y claim, completa canonical_question_en: pregunta en inglés, autocontenida, neutra y normalizada, sin cortesías y con términos estándar (por ejemplo seed round, venture capital y países en inglés). Redacciones equivalentes deben producir exactamente la misma cadena. has_entity es true solo si nombra una empresa, persona, inversor o evento concreto; false para estadísticas o listas sin entidad concreta.
Un mensaje con datos del perfil devuelve UNA sola parte profile con todos los campos juntos. Conserva todas las afirmaciones y nombres del mensaje tal como aparecen, incluso si parecen dudosos o mal transcritos; no descartes datos por incertidumbre ni sustituyas nombres por otros. Usa los nombres tal cual en startup_name, competitors y follows. Si una descripción identifica el producto, sector, ubicación o ronda, guárdala en los campos correspondientes y conserva detalles adicionales en one_liner/new_facts cuando aplique. Ejemplo: 'Somos Saiflow, software para hoteles en Barcelona' conserva startup_name=Saiflow, sector=hotel technology, location=Barcelona y one_liner con el software para hoteles.
Ejemplo: 'Somos Stayflow en Barcelona; nos interesan las fintech nórdicas' → una parte profile, profile_patch con startup_name=Stayflow, location=Barcelona, interests.sectors=[fintech], interests.regions=[Nordics].
Ejemplo literal: 'Somos Stayflow en Barcelona; nos interesan las fintech nórdicas en etapa seed y quiero saber quién invirtió en Wolt.' → una parte profile con profile_patch={{startup_name: 'Stayflow', location: 'Barcelona', interests: {{sectors: ['fintech'], regions: ['Nordics'], stages: ['SEED']}}}} y una parte query con canonical_question_en='Who invested in Wolt?' y has_entity=true. No omitas location, sector, región ni etapa cuando están mencionados.
Ejemplo mixto: 'somos Stayflow en Barcelona y quiero saber quién invirtió en Mews' produce profile con startup_name Stayflow/location Barcelona e intereses si se indican, y query sobre inversores de Mews.
Normaliza interests.sectors a uno de estos valores: {', '.join(SECTORS)}. regions en inglés canónico (Nordics, Spain, Finland). stages en códigos de Cala, por ejemplo SEED, SERIES_A, SERIES_B. En profile_patch incluye solo los datos explícitos; omite campos desconocidos o vacíos. Para campos ajenos a profile usa null/false según el schema. Aunque el mensaje se divida en varias partes profile, no descartes datos: cada parte debe contener los atributos explícitos que le correspondan."""


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
