"""Cálculo local, explicable y determinista de afinidad."""
import re
import math
from datetime import date
from statistics import quantiles
from .regions import country_of, region_match, REGIONS

WEIGHTS = {"sector": .30, "stage": .20, "region": .15, "ticket": .15, "activity": .10, "closeness": .10}
_STAGES = {"preseed":"pre-seed", "pre seed":"pre-seed", "pre-seed":"pre-seed", "seed":"seed", "a":"series a", "series_a":"series a", "serie a":"series a", "series a":"series a", "b":"series b", "series_b":"series b", "serie b":"series b", "series b":"series b", "c":"series c", "series_c":"series c", "serie c":"series c", "series c":"series c", "d":"series d", "series_d":"series d", "series d":"series d"}
_SYNONYMS = [set(x.split("|")) for x in ("fintech|financial services|payments", "saas|software|b2b software", "ai|artificial intelligence|machine learning", "healthtech|health|digital health", "climate|cleantech|energy", "proptech|real estate", "hospitality|travel|traveltech")]

def norm_stage(value):
    """Normaliza etapas conocidas."""
    if value is None: return None
    s = re.sub(r"\s+", " ", str(value).strip().casefold().replace("_", " "))
    s = re.sub(r"^serie\s+", "series ", s)
    return _STAGES.get(s) or ("pre-seed" if s.replace(" ", "") == "preseed" else s or None)

def parse_amount(value):
    """Extrae importes y convierte rangos a su punto medio."""
    if isinstance(value, (int, float)): return float(value)
    if not isinstance(value, str): return None
    s = value.casefold().replace(",", "").replace("–", "-").replace("—", "-")
    nums = re.findall(r"\d+(?:\.\d+)?", s)
    def one(part):
        m = re.search(r"(\d+(?:\.\d+)?)\s*(bn|billion|m|million|mm|k|thousand)?", part)
        if not m: return None
        n, unit = float(m.group(1)), m.group(2)
        return n * (1e9 if unit in ("bn", "billion") else 1e6 if unit in ("m", "million", "mm") else 1e3 if unit in ("k", "thousand") else 1)
    unit = re.search(r"(bn|billion|m|million|mm|k|thousand)\b", s)
    suffix = unit.group(1) if unit else None
    vals = [one(n + (suffix or "")) for n in nums]
    vals = [v for v in vals if v is not None]
    return sum(vals) / len(vals) if vals else None

def _sector_key(v): return re.sub(r"[^\w\s]", " ", str(v).casefold()).strip()
def sector_match(a, b):
    """Compara sectores por texto y grupos de sinónimos."""
    if not a or not b: return False
    x, y = _sector_key(a), _sector_key(b)
    if x == y or re.search(r"\b" + re.escape(x) + r"\b", y) or re.search(r"\b" + re.escape(y) + r"\b", x): return True
    return any(any(t in x for t in group) and any(t in y for t in group) for group in _SYNONYMS)

def _sources(*groups):
    out, seen = [], set()
    for group in groups:
        for source in group or []:
            if not isinstance(source, dict): continue
            key = source.get("url") or source.get("name")
            if key and key not in seen: seen.add(key); out.append(source)
            if len(out) == 5: return out
    return out

def _rounds(candidate): return [r for r in candidate.get("rounds", []) if r.get("sources")]
def _round_name(round_): return round_.get("round_type")
def _year(value):
    m = re.search(r"(?:19|20)\d{2}", str(value)) if value is not None else None
    return int(m.group()) if m else None
def _fmt(n):
    if n >= 1e9: return f"{n/1e9:g}B"
    if n >= 1e6: return f"{n/1e6:g}M"
    if n >= 1e3: return f"{n/1e3:g}K"
    return f"{n:g}"

def score_candidate(profile, candidate, *, today=None, weights=WEIGHTS):
    """Calcula puntaje y señales con datos trazables."""
    today = today or date.today(); rounds = _rounds(candidate); attrs = candidate.get("attrs") or {}
    attr_ok = bool(attrs.get("sources")); signals = []
    def add(name, value, text="", sources=()):
        signals.append({"signal":name,"value":value,"weight":weights[name],"text":text,"sources":_sources(sources)})
    sectors = profile.get("sectors") or []; sr = [r for r in rounds if r.get("sector")]
    if not sectors: add("sector", None)
    elif sr:
        n = sum(any(sector_match(r["sector"], s) for s in sectors) for r in sr); add("sector",n/len(sr),f"{n} of {len(sr)} tracked rounds in {sectors[0]}",[s for r in sr for s in r.get("sources",[])])
    elif attr_ok and attrs.get("industries"):
        inds=attrs["industries"]; ok=any(sector_match(i,s) for i in inds for s in sectors); label=inds[0]
        add("sector",float(ok),f"Operates in {label}" if ok else f"Operates in {label}, outside your sectors",attrs["sources"])
    else: add("sector",None)
    stage_labels=list(dict.fromkeys(x for x in ([profile.get("stage")] + (profile.get("stages") or [])) if norm_stage(x)))
    stages={norm_stage(x) for x in stage_labels}
    feats=candidate.get("features") or {}; feature_sources=feats.get("sources") or []
    typed=[r for r in rounds if _round_name(r)]
    if not stages: add("stage",None)
    elif not typed and feature_sources:
        vals=feats.get("stages") or []; hit=next((x for x in vals if norm_stage(x) in stages),None); label=hit or (vals[0] if vals else "")
        value=float(hit is not None); text=(f"Invests at {label}" if candidate.get("type")=="investor" and hit else f"Stage: {label}" if hit else f"Stage: {label}, outside your target stage")
        if _ai_tagged(attrs.get("ai_tagged"), "stages"): text += " (AI-tagged)"
        add("stage",value,text,feature_sources)
    elif not typed: add("stage",None)
    elif candidate.get("type")=="startup":
        latest=max(enumerate(typed),key=lambda p:(_year(p[1].get("year")) or -1,p[0]))[1]; st=norm_stage(_round_name(latest)); year=_year(latest.get("year")); add("stage",float(st in stages),f"Latest round: {_round_name(latest)}"+(f" ({year})" if year else ""),latest["sources"])
    else:
        counts=[sum(norm_stage(_round_name(r))==norm_stage(label) for r in typed) for label in stage_labels]; best=stage_labels[counts.index(max(counts))] if counts else stage_labels[0]
        n=sum(norm_stage(_round_name(r)) in stages for r in typed); add("stage",n/len(typed),f"{n} of {len(typed)} tracked rounds at {best}",[s for r in typed for s in r.get("sources",[])])
    regions=profile.get("regions") or []; located=[r for r in rounds if r.get("location")]
    if not regions: add("region",None)
    elif located:
        vals=[max(region_match(r["location"],x) for x in regions) for r in located]; n=sum(v==1 for v in vals); partial=sum(v==.6 for v in vals)
        counts=[sum(region_match(r["location"],x) for r in located) for x in regions]; label=regions[counts.index(max(counts))]
        add("region",sum(vals)/len(vals),f"{n} of {len(vals)} tracked rounds in {label}" if n else f"{partial} of {len(vals)} tracked rounds in {label}",[s for r in located for s in r["sources"]])
    elif attr_ok and (attrs.get("country") or attrs.get("hq")):
        loc=attrs.get("country") or attrs.get("hq"); val=max(region_match(loc,x) for x in regions); add("region",val,f"Headquartered in {country_of(loc) or loc}",attrs["sources"])
    else: add("region",None)
    if signals[0]["value"] is not None and not rounds and _ai_tagged(attrs.get("ai_tagged"), "sectors"): signals[0]["text"] += " (AI-tagged)"
    ticket=profile.get("ticket") or {}; lo=parse_amount(ticket.get("min")); hi=parse_amount(ticket.get("max")); amounts=[parse_amount(r.get("funding_amount")) for r in rounds]; amounts=[x for x in amounts if x]
    if (lo is None and hi is None): add("ticket",None)
    elif not amounts and feature_sources and isinstance(feats.get("amount"),dict) and (feats["amount"].get("min") is not None or feats["amount"].get("max") is not None):
        a=parse_amount(feats["amount"].get("min")); b=parse_amount(feats["amount"].get("max")); a=b if a is None else a; b=a if b is None else b
        lo,hi=(hi,lo) if lo is None else (lo,hi); lo,hi=(lo,lo) if hi is None else (lo,hi)
        overlap=not (b<lo or a>hi); near=min((abs(math.log10(x/y)) for x in (a,b) for y in (lo,hi) if x and y),default=1); value=1.0 if overlap else max(0,1-near)
        add("ticket",value,f"Typical round size {_fmt(a)}–{_fmt(b)}; your range is {_fmt(lo)}–{_fmt(hi)}",feature_sources)
    elif not amounts: add("ticket",None)
    else:
        lo,hi=(hi,lo) if lo is None else (lo,hi); lo,hi=(lo,lo) if hi is None else (lo,hi)
        if candidate.get("type")=="startup": typical=[max(enumerate([r for r in rounds if parse_amount(r.get("funding_amount"))]),key=lambda p:(_year(p[1].get("year")) or -1,p[0]))[1]]
        else:
            q=quantiles(amounts,n=4,method="inclusive") if len(amounts)>1 else [amounts[0]]*3; typical=q[0],q[2]
        a=parse_amount(typical[0].get("funding_amount")) if isinstance(typical,list) else typical[0]; b=parse_amount(typical[0].get("funding_amount")) if isinstance(typical,list) else typical[1]
        overlap=not (b<lo or a>hi); near=min((abs(math.log10(x/y)) for x in (a,b) for y in (lo,hi) if x and y),default=1)
        value=1.0 if overlap else max(0,1-near); add("ticket",value,f"Typical round size {_fmt(a)}–{_fmt(b)}; you are raising {_fmt(lo)}" if lo==hi else f"Typical round size {_fmt(a)}–{_fmt(b)}; your range is {_fmt(lo)}–{_fmt(hi)}",[s for r in rounds if parse_amount(r.get("funding_amount")) for s in r["sources"]])
    years=[(r,_year(r.get("year"))) for r in rounds]; dated=[(r,y) for r,y in years if y is not None]; cutoff=today.year-2; recent=[(r,y) for r,y in dated if y>=cutoff]
    if not dated and feature_sources and isinstance(feats.get("activity"),dict) and feats["activity"].get("rounds_24m") is not None:
        act=feats["activity"]; n=max(0,int(act["rounds_24m"])); led=act.get("led_24m"); txt=f"Led {led} and joined {max(0,n-int(led))} rounds in the last 24 months" if led is not None else f"{n} rounds in the last 24 months"
        add("activity",min(n,5)/5,txt,feature_sources)
    elif not dated: add("activity",None)
    else:
        leads=sum(bool(r.get("is_lead")) for r,y in recent); n=len(recent); txt=(f"Led {leads} and joined {n-leads} rounds since {cutoff}" if any("is_lead" in r for r,y in recent) else f"{n} rounds since {cutoff}") if n else f"No tracked rounds since {cutoff}"
        add("activity",min(n,5)/5,txt,[s for r,y in (recent or dated) for s in r["sources"]])
    distance=candidate.get("distance")
    if not profile.get("seeds"): add("closeness",None)
    elif distance is None: add("closeness",0,"No path to your network in the explored graph")
    elif not candidate.get("distance_sources"): add("closeness",None)
    else:
        val=1 if distance<=1 else .6 if distance==2 else .3 if distance==3 else 0
        txt="Directly connected to your network" if distance<=1 else f"{distance} hops from your network in the explored graph"
        add("closeness",val,txt,candidate["distance_sources"])
    known=[s for s in signals if s["value"] is not None]; denom=sum(weights.values()); score=round(100*sum(s["weight"]*s["value"] for s in known)/sum(s["weight"] for s in known)) if known else 0
    why=sorted((s for s in known if s["value"]>0 and s["sources"]),key=lambda s:s["weight"]*s["value"],reverse=True)[:2]
    return {"id":candidate.get("id"),"name":candidate.get("name"),"type":candidate.get("type"),"score":score,"confidence":round(sum(s["weight"] for s in known)/denom,2),"signals":signals,"why_match":why}

def rank(results):
    """Ordena resultados con desempates estables."""
    return sorted(results,key=lambda x:(-x.get("score",0),-x.get("confidence",0),(x.get("name") or "").casefold(),str(x.get("id") or "")))

def _ai_tagged(value, field):
    return value is True or isinstance(value, (list, tuple, set)) and field in value
