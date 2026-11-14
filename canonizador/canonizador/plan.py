ROUND = "PARTICIPATES_IN_FUNDING_ROUND"
CORP = "PARTICIPATES_IN_CORPORATE_EVENT"
import math
import re
import unicodedata

LIST_FILTERS = ("location", "sector", "min_funding", "round_label")
SECTOR_ALIASES = {
    "hotel tech": "hotel technology", "hotel technology": "hotel technology",
    "tecnologia hotelera": "hotel technology", "tecnologia de hoteles": "hotel technology",
    "climate tech": "climate tech", "fintech": "fintech", "healthtech": "healthtech",
    "saas": "saas", "ai": "ai", "artificial intelligence": "ai", "cybersecurity": "cybersecurity",
    "edtech": "edtech", "proptech": "proptech", "mobility": "mobility", "foodtech": "foodtech",
    "biotech": "biotech", "ecommerce": "ecommerce", "e-commerce": "ecommerce",
    "logistics": "logistics", "gaming": "gaming", "other": "other",
}
LOCATION_ALIASES = {"espana": "Spain", "spain": "Spain", "estados unidos": "United States", "united states": "United States", "reino unido": "United Kingdom", "united kingdom": "United Kingdom"}


def _ascii(value):
    return "".join(c for c in unicodedata.normalize("NFD", str(value)) if unicodedata.category(c) != "Mn")


def effective_attribute(intent):
    attr, filters = intent.get("attribute"), intent.get("filters", {})
    if attr != "company_list" and not intent.get("entities") and any(filters.get(k) not in (None, "") for k in LIST_FILTERS):
        return "company_list"
    return attr

def build_query(intent, company_name=None):
    """Renderiza la intención en una consulta fija, sin intervención del LLM."""
    attr, f = effective_attribute(intent), intent.get("filters", {})
    name = company_name or (intent.get("entities") or [{}])[0].get("name", "")
    if attr in ("funding_round", "lead_investors"):
        label = str(f.get("round_label") or "").upper().replace("SERIES_", "").replace("SERIES ", "").replace("_", " ")
        label = {"SEED": "Seed", "PRE SEED": "Pre_Seed"}.get(label, label)
        q = f"{name}.funding_round" + (f".series={label}" if label else "")
        return q + ".return(amount, lead investor, investors, date)"
    templates = {
        "total_funding": f"{name}.return(total funding)",
        "investors": f"{name}.investors.return(name, is_lead)",
        "founders": f"{name}.founders.return(name)",
        "executives": f"{name}.executives.return(name, title)",
        "headcount": f"{name}.return(employee count)",
        "acquisitions": f"{name}.acquisitions.return(name, date, amount)",
        "profile": f"{name}.return(name, description, sector, location, funding, employee count)",
        "event_attendees": f"{name}.event_attendees.return(name)",
    }
    if attr == "company_list":
        parts = ["startups"]
        if f.get("location"):
            loc_key = _ascii(f["location"]).strip().casefold()
            location = LOCATION_ALIASES.get(loc_key, " ".join(w.capitalize() for w in _ascii(f["location"]).split()))
            parts.append(f"location={location}")
        if f.get("sector"):
            sector_key = _ascii(f["sector"]).strip().casefold()
            sector = SECTOR_ALIASES.get(sector_key, "other")
            parts.append(f"sector={sector}")
        if f.get("min_funding") not in (None, ""): parts.append(f"funding>{_funding_literal(f['min_funding'])}")
        return ".".join(parts) + ".return(name, funding, sector, location)"
    if attr == "other": return ""
    return templates[attr]

def _funding_literal(value):
    if isinstance(value, bool): raise ValueError("min_funding debe ser un número")
    try:
        text = str(value).strip().replace(",", "")
        if not re.fullmatch(r"\d+(?:\.\d+)?", text): raise ValueError
        n = float(text)
    except (TypeError, ValueError):
        raise ValueError("min_funding debe ser un número en moneda base") from None
    if not math.isfinite(n) or n < 0: raise ValueError("min_funding debe ser un número no negativo")
    if n >= 1_000_000_000: return f"{n/1_000_000_000:g}B"
    if n >= 1_000_000: return f"{n/1_000_000:g}M"
    if n >= 1000: return f"{n/1000:g}K"
    return f"{n:g}"


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
