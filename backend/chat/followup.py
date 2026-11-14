"""Convierte un mensaje que depende del anterior ("¿esto es verdad?", "¿y su CEO?") en uno autocontenido.

Solo resuelve referencias con lo que ya se dijo en la conversación; no añade datos nuevos.
"""
import json

SCHEMA = {"type": "object", "additionalProperties": False, "required": ["text"],
          "properties": {"text": {"type": "string"}}}

SYSTEM = ("Rewrite the user's new message so it can be understood without the conversation, replacing pronouns and "
          "references (this, that, it, esto, eso, su, ellos...) with the names, companies or figures they refer to in "
          "the recent messages. Keep the user's language and intent (question stays a question, claim stays a claim). "
          "Do not add any fact that is not in the recent messages. If the message is already self-contained, return it "
          "unchanged.")


async def self_contained(text, history, llm):
    recent = [{"role": m.get("role"), "text": m.get("text")} for m in history[-4:] if m.get("text")]
    if not recent:
        return text
    try:
        result = await llm.complete_json(SYSTEM, json.dumps({"recent_messages": recent, "new_message": text}, ensure_ascii=False), SCHEMA)
    except Exception:
        return text
    rewritten = (result.get("text") or "").strip() if isinstance(result, dict) else ""
    return rewritten or text
