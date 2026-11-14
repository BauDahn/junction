ROUND = "PARTICIPATES_IN_FUNDING_ROUND"
CORP = "PARTICIPATES_IN_CORPORATE_EVENT"


def build_plan(intent, entity_id):
    attr, filters = intent["attribute"], intent.get("filters", {})
    rel = {}
    props = []
    if attr in ("funding_round", "lead_investors"):
        # Local filters are retained separately; only `request` is sent to Cala.
        rel = {"outgoing": {ROUND: {"limit": 100}}}
        return [{"entity_id": entity_id, "request": {"properties": ["name"], "relationships": rel}, "filters": {"issuer_role": "ISSUER", **{k: v for k, v in filters.items() if v}}}, {"follow": "funding_round_participants", "relationship": ROUND, "direction": "incoming", "filters": {"is_lead": True} if attr == "lead_investors" else {}}]
    mapping = {"investors": ("incoming", "INVESTED_IN"), "founders": ("incoming", "FOUNDED"), "executives": ("incoming", "IS_CEO_OF"), "acquisitions": ("outgoing", CORP), "event_attendees": ("incoming", "PARTICIPATES_IN_EVENT")}
    if attr in mapping:
        direction, relation = mapping[attr]
        rel = {direction: {relation: {"limit": 100, "offset": 0}}}
    if attr in ("total_funding", "profile", "headcount"):
        props = ["name", "description", "total_funding", "total_funding_units", "employee_count_range", "founding_date", "headquarters_address"]
        return [{"entity_id": entity_id, "properties": props, "relationships": {}, "numerical_observations": ["Number of employees"] if attr == "headcount" else []}]
    if attr == "other": return [{"fallback": "knowledge/search"}]
    return [{"entity_id": entity_id, "properties": props, "relationships": rel}]
