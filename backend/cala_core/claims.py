import json


SCHEMA = {"type": "object", "additionalProperties": False, "required": ["verdict", "explanation"],
          "properties": {"verdict": {"type": "string", "enum": ["confirmed", "partially_confirmed", "contradicted", "no_data"]},
                         "explanation": {"type": "string"}}}
SYSTEM = "Compara la afirmación del usuario exclusivamente con la evidencia estructurada de Cala. Sin evidencia pertinente: no_data (nunca contradicción). Redondeo y moneda equivalente cuentan como confirmed. Si solo parte de la afirmación coincide, partially_confirmed. Si evidencia suficiente contradice el valor, contradicted. Una frase breve; no agregues datos."


async def check(part, evidence, llm):
    claim = part.get("claim") or part.get("text", "")
    user = json.dumps({"claim": claim, "subject": part.get("subject"), "attribute": part.get("attribute"),
                       "user_value": part.get("user_value"), "cala_evidence": evidence}, ensure_ascii=False)
    result = await llm.complete_json(SYSTEM, user, SCHEMA)
    verdict = result.get("verdict", "no_data")
    if verdict not in {"confirmed", "partially_confirmed", "contradicted", "no_data"}: verdict = "no_data"
    block = evidence if evidence and evidence.get("type") in {"cala_table", "cala_answer"} else None
    return {"type": "claim_check", "claim": claim, "verdict": verdict,
            "explanation": result.get("explanation", "Sin evidencia suficiente de Cala."), "evidence": block,
            "sources": (block or {}).get("sources", [])}
