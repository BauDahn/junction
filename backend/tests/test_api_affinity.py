from datetime import date
import pytest
from api.affinity import score_candidate, parse_amount, norm_stage, sector_match, rank
from api.regions import country_of, region_match

SRC=[{"name":"Cala", "url":"https://cala.test"}]
def round_(**kw): return {"company":"Acme", "sources":SRC, **kw}

@pytest.mark.parametrize("value,expected", [("$3.2M",3_200_000),("€30 million",30_000_000),("over 100M",100_000_000),("~206,753",206753),("$710–717 million",713_500_000),(500000,500000),("500k",500000),("1.5bn",1_500_000_000),("unknown",None)])
def test_parse_amount(value,expected): assert parse_amount(value)==expected

@pytest.mark.parametrize("value,expected", [("Series A","series a"),("series_a","series a"),("Serie A","series a"),("A","series a"),("Pre-Seed","pre-seed"),("preseed","pre-seed"),("Seed","seed"),("",None)])
def test_norm_stage(value,expected): assert norm_stage(value)==expected

def test_sector_synonyms_and_containment():
    assert sector_match("fintech","Financial Services") and sector_match("AI","Artificial Intelligence")
    assert sector_match("Fintech / Payments","fintech") and not sector_match("food","health")

@pytest.mark.parametrize("text,expected", [("Madrid","Spain"),("Madrid, Spain","Spain"),("España","Spain"),("Finland","Finland"),("Helsinki, Uusimaa, Finland","Finland"),("UK","United Kingdom"),("DE","Germany")])
def test_country_of(text,expected): assert country_of(text)==expected

def test_region_match():
    assert region_match("Spain","Madrid")==1
    assert region_match("Finland","Nordics")==.6
    assert region_match("Spain","Germany")==0
    assert region_match("Spain","Europe")==.6

def test_sector_stage_and_missing_sources():
    c={"id":"1","name":"Fund","type":"investor","rounds":[round_(sector="Fintech",round_type="Seed"),{"sector":"Fintech","round_type":"Seed"}]}
    p=score_candidate({"sectors":["fintech"],"stage":"Seed"},c)
    assert p["signals"][0]["value"]==1 and "1 of 1" in p["signals"][0]["text"]
    assert p["signals"][1]["value"]==1 and p["confidence"]==.5

def test_attrs_requires_sources():
    c={"attrs":{"industries":["Fintech"]}}
    assert score_candidate({"sectors":["Fintech"]},c)["signals"][0]["value"] is None

def test_score_formula_and_why():
    c={"id":"f","name":"Fund","type":"investor","rounds":[round_(sector="Fintech",round_type="Seed",location="Spain",funding_amount="3M",year="2025",is_lead=True)]}
    p=score_candidate({"sectors":["Fintech"],"stage":"Seed","regions":["Spain"],"ticket":{"min":2_000_000,"max":4_000_000},"seeds":["x"]},{**c,"distance":1,"distance_sources":SRC},today=date(2026,1,1))
    assert p["score"]==100 and p["confidence"]==1
    assert [x["signal"] for x in p["why_match"]]==["sector","stage"]
    assert all(x["sources"] for x in p["why_match"])

def test_region_and_ticket_values():
    c={"type":"investor","rounds":[round_(location="Finland",funding_amount="1M",round_type="Seed")]}
    p=score_candidate({"regions":["Nordics"],"ticket":{"min":10_000_000,"max":10_000_000}},c)
    assert p["signals"][2]["value"]==.6 and p["signals"][3]["value"]==0
    c["rounds"]=[round_(funding_amount="3M")]
    assert score_candidate({"ticket":{"min":2_000_000,"max":4_000_000}},c)["signals"][3]["value"]==1

def test_activity_today_and_startup_latest():
    c={"type":"investor","rounds":[round_(year="2025-03-01",is_lead=True) for _ in range(7)]}
    a=score_candidate({},c,today=date(2026,1,1))["signals"][4]
    assert a["value"]==1 and a["text"]=="Led 7 and joined 0 rounds since 2024"
    s={"type":"startup","rounds":[round_(round_type="Seed",year="2024"),round_(round_type="Series A",year="2025")]}
    assert score_candidate({"stage":"Series A"},s)["signals"][1]["value"]==1

@pytest.mark.parametrize("distance,value", [(1,1),(2,.6),(3,.3),(5,0)])
def test_closeness(distance,value):
    sig=score_candidate({"seeds":["x"]},{"distance":distance,"distance_sources":SRC})["signals"][-1]
    assert sig["value"]==value

def test_closeness_missing():
    assert score_candidate({"seeds":["x"]},{"distance":None})["signals"][-1]["value"]==0
    assert score_candidate({}, {"distance":1,"distance_sources":SRC})["signals"][-1]["value"] is None
    assert score_candidate({"seeds":["x"]},{"distance":1})["signals"][-1]["value"] is None

def test_rank_and_calibration():
    assert [x["name"] for x in rank([{"name":"B","score":2,"confidence":.5},{"name":"A","score":2,"confidence":.7}])]==["A","B"]
    good={"type":"investor","rounds":[round_(sector="Fintech",round_type="Seed",location="Spain",funding_amount="2M",year="2025")],"distance":1,"distance_sources":SRC}
    p={"sectors":["fintech"],"stage":"Seed","regions":["Spain"],"ticket":{"min":2_000_000,"max":2_000_000},"seeds":["x"]}
    assert score_candidate(p,good,today=date(2026,1,1))["score"]>=80
    bad={"type":"investor","rounds":[round_(sector="Healthcare",round_type="Series C",location="USA",funding_amount="200M",year="2019")],"distance":None}
    assert score_candidate(p,bad,today=date(2026,1,1))["score"]<40
