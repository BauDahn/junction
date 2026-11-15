"""Investor profiling with a reproducible Cala query."""
import re
from cala_core.executor import _sources

INVESTOR_QUERY = "startups.investors={name}.return(company, round_type, funding_amount, year, sector, location)"

def investor_query(name):
    """Builds a query using a name safe for Cala query syntax."""
    clean = re.sub(r"[.,()=]", " ", str(name or ""))
    return INVESTOR_QUERY.format(name=" ".join(clean.split()))

def rounds_from_result(result, query):
    """Converts Cala rows into rounds with normalized sources."""
    def key(k): return re.sub(r"[\s-]+", "_", str(k).casefold()).strip("_")
    def sources(data):
        found = _sources(data)
        return found or []
    response_sources = sources(result)
    rounds = []
    aliases = {"company":("company","name"),"round_type":("round_type",),"funding_amount":("funding_amount","funding","amount"),"year":("year","date"),"sector":("sector",),"location":("location",)}
    for row in result.get("results", []):
        if not isinstance(row, dict): continue
        fields = {key(k):v for k,v in row.items()}
        company = next((fields[k] for k in aliases["company"] if fields.get(k) not in (None,"")), None)
        if not company: continue
        item = {"company":company}
        for target, names in list(aliases.items())[1:]:
            value = next((fields[k] for k in names if fields.get(k) not in (None,"")), None)
            if value is not None: item[target] = value
        lead = fields.get("is_lead")
        if lead is not None: item["is_lead"] = lead
        item["sources"] = sources(row) or response_sources or [{"name":f"Cala knowledge/query: {query}"}]
        rounds.append(item)
    return rounds

async def investor_rounds(cala, name):
    """Fetches all known investor rounds in one query."""
    query = investor_query(name)
    result = await cala.knowledge_query(query)
    if not isinstance(result.get("results"), list): raise TypeError("Cala results must be a list")
    entities = {}
    def add(entity):
        if isinstance(entity, dict) and entity.get("name") and entity.get("id") is not None:
            entities[str(entity["name"]).casefold()] = entity["id"]
    for entity in result.get("entities", []) or []:
        add(entity)
        for mention in entity.get("mentions", []) or []: add(mention)
    return {"query":query,"rounds":rounds_from_result(result,query),"entities":entities}
