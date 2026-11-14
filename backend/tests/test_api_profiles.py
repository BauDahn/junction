import pytest
from api.profiles import investor_query, rounds_from_result, investor_rounds

def test_query_template_and_cleaning():
    assert investor_query("Acme Fund") == "startups.investors=Acme Fund.return(company, round_type, funding_amount, year, sector, location)"
    assert investor_query(" A.B, C=(D) ")=="startups.investors=A B C D.return(company, round_type, funding_amount, year, sector, location)"

def test_rows_variations_and_synthetic_source():
    query=investor_query("Fund")
    result={"results":[{"name":"Startup","round type":"Series A","funding amount":"$3M","date":"Mar 2025","sector":"AI","location":"Helsinki"},{"round type":"Seed"}]}
    rows=rounds_from_result(result,query)
    assert rows==[{"company":"Startup","round_type":"Series A","funding_amount":"$3M","year":"Mar 2025","sector":"AI","location":"Helsinki","sources":[{"name":f"Cala knowledge/query: {query}"}]}]

def test_real_row_sources():
    q="query"; result={"results":[{"company":"A","funding":"5M","sources":[{"name":"TechCrunch","url":"https://example.test"}]}]}
    assert rounds_from_result(result,q)[0]["sources"]==[{"name":"TechCrunch","url":"https://example.test"}]

class Cala:
    def __init__(self,result): self.result=result; self.calls=[]
    async def knowledge_query(self,input): self.calls.append(input); return self.result

@pytest.mark.asyncio
async def test_one_query_and_entities_mentions():
    cala=Cala({"results":[{"company":"Acme","amount":"$1M"}],"entities":[{"id":"1","name":"Acme Fund","mentions":[{"id":"2","name":"Acme"}]}]})
    out=await investor_rounds(cala,"Acme Fund")
    assert len(cala.calls)==1 and out["entities"]=={"acme fund":"1","acme":"2"}
    assert out["rounds"][0]["funding_amount"]=="$1M"

@pytest.mark.asyncio
async def test_non_list_results_raises():
    with pytest.raises(TypeError): await investor_rounds(Cala({"results":None}),"Fund")
