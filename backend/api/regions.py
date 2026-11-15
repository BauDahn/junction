"""Countries and regions used for affinity."""

_COUNTRIES = {
    "Finland": ["finland", "suomi", "finlandia"], "Sweden": ["sweden", "sverige", "suecia"],
    "Norway": ["norway", "norge", "noruega"], "Denmark": ["denmark", "danmark", "dinamarca"],
    "Iceland": ["iceland", "island", "islandia"], "Germany": ["germany", "de", "deutschland", "alemania"],
    "Austria": ["austria", "österreich", "austria"], "Switzerland": ["switzerland", "ch", "schweiz", "suisse", "suiza"],
    "Spain": ["spain", "españa", "espana"], "Portugal": ["portugal"], "France": ["france", "francia"],
    "United Kingdom": ["uk", "united kingdom", "great britain", "britain", "england", "gb"],
    "Ireland": ["ireland", "éire", "eire"], "Netherlands": ["netherlands", "the netherlands", "holland"],
    "Belgium": ["belgium", "belgië", "belgique"], "Luxembourg": ["luxembourg"],
    "Estonia": ["estonia"], "Latvia": ["latvia"], "Lithuania": ["lithuania"],
    "Italy": ["italy", "italia"], "Greece": ["greece", "hellas"], "Croatia": ["croatia"],
    "Slovenia": ["slovenia"], "Poland": ["poland", "polska"], "Czechia": ["czechia", "czech republic"],
    "Slovakia": ["slovakia"], "Hungary": ["hungary"], "Romania": ["romania"], "Bulgaria": ["bulgaria"],
    "Ukraine": ["ukraine"], "Serbia": ["serbia"], "United States": ["usa", "us", "united states", "america"],
}
_HUBS = {"Madrid":"Spain", "Barcelona":"Spain", "Valencia":"Spain", "Lisbon":"Portugal", "Helsinki":"Finland", "Espoo":"Finland", "Stockholm":"Sweden", "Oslo":"Norway", "Copenhagen":"Denmark", "Berlin":"Germany", "Munich":"Germany", "Vienna":"Austria", "Zurich":"Switzerland", "Geneva":"Switzerland", "Paris":"France", "London":"United Kingdom", "Amsterdam":"Netherlands", "Rotterdam":"Netherlands", "Tallinn":"Estonia", "Dublin":"Ireland", "Milan":"Italy", "Rome":"Italy", "Athens":"Greece", "Prague":"Czechia", "Warsaw":"Poland", "Brussels":"Belgium"}
_LOOKUP = {x.casefold(): country for country, names in _COUNTRIES.items() for x in [country, *names]}
_LOOKUP.update({k.casefold(): v for k, v in _HUBS.items()})
_EUROPE = set(_COUNTRIES) - {"United States"}
REGIONS = {
    "Nordics": {"Finland", "Sweden", "Norway", "Denmark", "Iceland"},
    "DACH": {"Germany", "Austria", "Switzerland"}, "Iberia": {"Spain", "Portugal"},
    "Baltics": {"Estonia", "Latvia", "Lithuania"}, "Benelux": {"Netherlands", "Belgium", "Luxembourg"},
    "UK & Ireland": {"United Kingdom", "Ireland"}, "France": {"France"},
    "Southern Europe": {"Italy", "Greece", "Spain", "Portugal", "Croatia", "Slovenia"},
    "CEE": {"Poland", "Czechia", "Slovakia", "Hungary", "Romania", "Bulgaria", "Ukraine", "Serbia", "Croatia", "Slovenia"},
    "Europe": _EUROPE,
}
_REGION_NAMES = {k.casefold(): k for k in REGIONS}

def country_of(text):
    """Resolves a country from text or its components."""
    if not isinstance(text, str): return None
    whole = text.strip().casefold()
    if whole in _LOOKUP: return _LOOKUP[whole]
    parts = [p.strip().casefold() for p in text.split(",")]
    return next((_LOOKUP[p] for p in reversed(parts) if p in _LOOKUP), None)

def region_match(a, b):
    """Compares countries and regional groups for product affinity."""
    ca, cb = country_of(a), country_of(b)
    ra = _REGION_NAMES.get(a.strip().casefold()) if isinstance(a, str) else None
    rb = _REGION_NAMES.get(b.strip().casefold()) if isinstance(b, str) else None
    if ca and cb:
        if ca == cb: return 1.0
        if ca not in _EUROPE or cb not in _EUROPE: return 0.0
        if "Europe" in (ra, rb): return 0.6
        return 0.6 if any(ca in REGIONS[g] and cb in REGIONS[g] for g in REGIONS if g != "Europe") else 0.0
    if ca and rb: return 0.6 if ca in REGIONS[rb] else 0.0
    if cb and ra: return 0.6 if cb in REGIONS[ra] else 0.0
    if ra and rb: return 0.6 if REGIONS[ra] & REGIONS[rb] else 0.0
    if isinstance(a, str) and isinstance(b, str) and a.casefold() == b.casefold(): return 1.0
    return 0.0
