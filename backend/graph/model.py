"""Local graph model and normalization."""
from datetime import datetime, timezone
import re
import unicodedata
import hashlib
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
    # Scoring separately recognizes suffixes written as S.L. and S.R.L.
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

def rels_key(rels):
    if isinstance(rels, str):
        return rels
    values = sorted(set(rels or ()))
    return "rels:" + hashlib.sha1(",".join(values).encode()).hexdigest()[:12]

def node_is_expanded(node, rels, ttl_s=TTL_S):
    date = (node or {}).get("expanded", {}).get(rels_key(rels))
    if not date:
        return False
    try:
        parsed = datetime.fromisoformat(date)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - parsed.astimezone(timezone.utc)).total_seconds() < ttl_s
    except (ValueError, TypeError):
        return False
