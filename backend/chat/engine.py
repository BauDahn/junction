import json
import uuid
from . import store
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


async def handle_text(session_id, text, llm, transcript=None):
    profile = store.get_profile(session_id) or empty_profile()
    history = store.list_messages(session_id)[-10:]
    rec = store.get_recommendations(session_id)
    cards = []
    for category in ("investors", "competitors", "prospects"):
        cards.extend((rec["data"].get(category) or []) if rec and rec["status"] == "ready" else [])
    compact = [{"index":i,"type":c.get("type"),"title":c.get("title"),"reason":c.get("reason")} for i,c in enumerate(cards)]
    pending_notice = bool(rec and rec["status"] == "ready" and not rec["notified"])
    user = json.dumps({"current_profile": profile, "recent_messages": history, "new_message": text, "missing_fields": missing_fields(profile), "recommendation_cards":compact, "recommendations_ready":pending_notice}, ensure_ascii=False)
    result = await llm.complete_json(SYSTEM, user, SCHEMA)
    patch = result.get("profile_patch", {})
    updated, changed = merge(profile, patch)
    user_msg = {"id": uuid.uuid4().hex, "session_id": session_id, "role": "user", "text": text, "transcript": transcript, "sources": [], "cards": [], "created_at": store.now_iso()}
    reply_msg = {"id": uuid.uuid4().hex, "session_id": session_id, "role": "assistant", "text": result["reply"], "transcript": None, "sources": [], "cards": [], "created_at": store.now_iso()}
    used = result.get("used_cards") or []
    for idx in used:
        if isinstance(idx, int) and not isinstance(idx, bool) and 0 <= idx < len(cards):
            reply_msg["sources"].extend(s for s in cards[idx].get("sources", []) if s not in reply_msg["sources"])
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
