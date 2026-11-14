import json
import uuid
from . import store
from .profile import empty_profile, merge

SCHEMA = {"type": "object", "properties": {"reply": {"type": "string"}, "profile_patch": {"type": "object", "properties": {
    "startup_name": {"type": "string"}, "one_liner": {"type": "string"}, "sector": {"type": "string"}, "stage": {"type": "string"}, "location": {"type": "string"}, "raising_amount": {"type": "string"}, "raising_round": {"type": "string"}, "competitors": {"type": "array", "items": {"type": "string"}}, "target_customers": {"type": "string"}, "new_facts": {"type": "array", "items": {"type": "string"}}
}}}}

SYSTEM = "You help a startup founder build a factual startup profile. Extract only information the founder explicitly said; never invent. Reply in the user's language, briefly in 2-4 sentences, confirm what you understood and ask exactly ONE question that fills a missing profile field (sector, stage, city, competitors, or what they seek). Never assert market facts, investors, or external figures; those come from Cala elsewhere."


async def handle_text(session_id, text, llm):
    profile = store.get_profile(session_id) or empty_profile()
    history = store.list_messages(session_id)[-10:]
    user = json.dumps({"current_profile": profile, "recent_messages": history, "new_message": text}, ensure_ascii=False)
    result = await llm.complete_json(SYSTEM, user, SCHEMA)
    patch = result.get("profile_patch", {})
    updated, changed = merge(profile, patch)
    user_msg = {"id": uuid.uuid4().hex, "session_id": session_id, "role": "user", "text": text, "transcript": None, "sources": [], "cards": [], "created_at": store.now_iso()}
    reply_msg = {"id": uuid.uuid4().hex, "session_id": session_id, "role": "assistant", "text": result["reply"], "transcript": None, "sources": [], "cards": [], "created_at": store.now_iso()}
    return user_msg, reply_msg, updated if changed else None
