import uuid
from cala_core import handle_message as cala_handle_message
from verifier.config import settings
from . import store
from .focus import focus_table
from .profile import empty_profile, merge

SCHEMA = {"type": "object", "properties": {"reply": {"type": "string"}, "used_cards": {"type":"array", "items":{"type":"integer"}}, "profile_patch": {"type": "object", "properties": {
    "startup_name": {"type": "string"}, "one_liner": {"type": "string"}, "sector": {"type": "string"}, "stage": {"type": "string"}, "location": {"type": "string"}, "raising_amount": {"type": "string"}, "raising_round": {"type": "string"}, "competitors": {"type": "array", "items": {"type": "string"}}, "target_customers": {"type": "string"}, "new_facts": {"type": "array", "items": {"type": "string"}}
}}}}

SYSTEM = "You help a startup founder build a factual startup profile. Extract only information the founder explicitly said; never invent. Reply in the user's language, briefly in 2-4 sentences, confirm what you understood and ask exactly ONE question about a field listed in missing_fields (never about a field already in current_profile); if missing_fields is empty, ask what they need help with. Never assert market facts, investors, or external figures except from supplied recommendation cards. Use only supplied card data, cite used_cards by zero-based card index, and say you don't know when unsupported. If recommendations_ready is true, mention recommendations are ready in one sentence."


def missing_fields(profile):
    """Campos del perfil que todavía no tenemos, para que el chat no pregunte lo que ya sabe."""
    checks = {
        "what the startup does": profile.get("one_liner"),
        "sector": profile.get("sector"),
        "stage": profile.get("stage"),
        "city": profile.get("location"),
        "competitors": profile.get("competitors"),
        "target customers": profile.get("target_customers"),
        "what they are raising": (profile.get("raising") or {}).get("amount") or (profile.get("raising") or {}).get("round"),
    }
    return [name for name, value in checks.items() if not value]


async def handle_text(session_id, text, llm, transcript=None, cala=None, context=None):
    profile = store.get_profile(session_id) or empty_profile()
    rec = store.get_recommendations(session_id)
    pending_notice = bool(rec and rec["status"] == "ready" and not rec["notified"])
    # cala_core usa el cliente del canonizador (knowledge_query); el CalaClient del verificador no sirve aquí.
    core_cala = cala if hasattr(cala, "knowledge_query") else None
    result = await cala_handle_message(text, profile, llm, cala=core_cala, cache_dir=getattr(settings, "cache_dir", None))
    blocks = result.get("blocks", [])
    for block in blocks:
        if isinstance(block, dict) and block.get("type") == "cala_table":
            await focus_table(text, block, llm)
    patch = result.get("profile_patch", {})
    updated, changed = merge(profile, patch)
    user_msg = {"id": uuid.uuid4().hex, "session_id": session_id, "role": "user", "text": text, "transcript": transcript, "sources": [], "cards": [], "created_at": store.now_iso()}
    reply_sources = []
    for block in blocks:
        for source in block.get("sources", []) if isinstance(block, dict) else []:
            if source not in reply_sources: reply_sources.append(source)
    if len(blocks) == 1 and blocks[0].get("type") == "text":
        reply_text = blocks[0].get("text", "")
    elif (answers := [b["answer"] for b in blocks if b.get("answer")]) and len(answers) == 1:
        reply_text = answers[0]
    elif any(b.get("type") == "cala_table" or b.get("type") == "cala_answer" for b in blocks):
        reply_text = "Esto es lo que tiene Cala."
    elif any(b.get("type") == "claim_check" for b in blocks):
        reply_text = "Contrasté tu afirmación con Cala."
    elif any(b.get("type") == "profile_update" for b in blocks):
        reply_text = "Actualicé tu perfil."
    elif any(b.get("type") == "not_found" for b in blocks):
        reply_text = "Cala no tiene datos sobre esto; abajo lo que se buscó."
    else:
        reply_text = "De acuerdo."
    if pending_notice:
        reply_text = f"{reply_text} Tus recomendaciones están listas."
    reply_msg = {"id": uuid.uuid4().hex, "session_id": session_id, "role": "assistant", "text": reply_text, "transcript": None, "sources": reply_sources, "cards": [], "blocks": blocks, "created_at": store.now_iso()}
    if pending_notice:
        selected = []
        for category in ("investors", "competitors", "prospects"):
            group = rec["data"].get(category) or []
            if group:
                selected.append(group[0])
        reply_msg["cards"] = selected
        for card in selected:
            for source in card.get("sources", []):
                if source not in reply_msg["sources"]:
                    reply_msg["sources"].append(source)
        store.mark_notified(session_id)
    return user_msg, reply_msg, updated if changed else None
