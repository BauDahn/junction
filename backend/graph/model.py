"""Modelo y normalización del grafo local."""
from datetime import datetime, timezone
import re
import unicodedata
from urllib.parse import urlsplit

REL_WHITELIST = frozenset("INVESTED_IN PARTICIPATES_IN_FUNDING_ROUND FOUNDED IS_CEO_OF IS_CTO_OF IS_BOARD_MEMBER_OF WORKS_AT IS_MEMBER_OF PARTICIPATES_IN_CORPORATE_EVENT PARTICIPATES_IN_EVENT".split())
ATTRIBUTE_RELS = {"OPERATES_IN_INDUSTRY": "industries", "HAS_HEADQUARTERS_IN": "hq", "IS_REGISTERED_IN": "country", "HAS_DOMAIN_NAME": "domain"}
EXCLUDED_TYPES = frozenset("PrivateCompanyFundingRound Product Award Country Group EducationalInstitution".split())
TTL_S = 7 * 24 * 3600
PREFIX = "graph:v1:"
_SUFFIXES = ("s r l", "s l", "limited", "gmbh", "llp", "ltd", "inc", "oyj", "aps", "sas", "srl", "plc", "llc", "oy", "ab", "sa", "sl", "bv", "as")

def _plain(value):
    value = unicodedata.normalize("NFKD", str(value or "").casefold())
    return "".join(c for c in value if not unicodedata.combining(c))

def normalize_name(name):
    text = _plain(name)
    # Puntuar separada permite reconocer sufijos escritos como S.L. y S.R.L.
    text = re.sub(r"[^\w\s]", " ", text, flags=re.UNICODE)
    words = " ".join(text.split()).split()
    original = words[:]
    while words:
        suffix = next((s for s in _SUFFIXES if " ".join(words[-len(s.split()):]) == s), None)
        if not suffix: break
        del words[-len(suffix.split()):]
    return " ".join(words or original)

def types_compatible(a, b):
    return a == b or (a in {"Company", "Organization"} and b in {"Company", "Organization"})

def website_key(url):
    if not url: return None
    value = str(url).strip()
    if not value: return None
    parsed = urlsplit(value if "://" in value else "//" + value)
    host = (parsed.hostname or "").casefold()
    if host.startswith("www."): host = host[4:]
    return host or None

def now_iso():
    return datetime.now(timezone.utc).isoformat()
