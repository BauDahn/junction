import json


SCHEMA = {"type": "object", "additionalProperties": False, "required": ["verdict", "explanation"],
          "properties": {"verdict": {"type": "string", "enum": ["confirmed", "partially_confirmed", "contradicted", "no_data"]},
                         "explanation": {"type": "string"}}}
SYSTEM = "Compare the user's claim exclusively with Cala's structured evidence. If there is no relevant evidence, use no_data (never contradiction). Rounding and equivalent currencies count as confirmed. If only part of the claim matches, use partially_confirmed. If sufficient evidence contradicts the value, use contradicted. Write the brief explanation in English and add no facts."


async def check(part, evidence, llm):
    claim = part.get("claim") or part.get("text", "")
    user = json.dumps({"claim": claim, "subject": part.get("subject"), "attribute": part.get("attribute"),
                       "user_value": part.get("user_value"), "cala_evidence": evidence}, ensure_ascii=False)
    result = await llm.complete_json(SYSTEM, user, SCHEMA)
    verdict = result.get("verdict", "no_data")
    if verdict not in {"confirmed", "partially_confirmed", "contradicted", "no_data"}: verdict = "no_data"
    block = evidence if evidence and evidence.get("type") in {"cala_table", "cala_answer"} else None
    return {"type": "claim_check", "claim": claim, "verdict": verdict,
            "explanation": result.get("explanation", "Not enough evidence from Cala."), "evidence": block,
            "sources": (block or {}).get("sources", [])}
