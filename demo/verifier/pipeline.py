import asyncio
import inspect
import json
import time

from .cala import CalaClient
from .config import settings
from .llm import make_llm, strict_schema
from .pdf import read_pdf

CLAIMS_SCHEMA = strict_schema({
    "type": "object",
    "properties": {
        "startup_name": {"type": "string"},
        "claims": {"type": "array", "items": {"type": "object", "properties": {
            "id": {"type": "string"}, "page": {"type": "integer"},
            "quote": {"type": "string"},
            "category": {"type": "string", "enum": ["funding", "investor", "competitor", "customer", "partner", "market", "team", "traction", "other"]},
            "publicly_verifiable": {"type": "boolean"}, "cala_question": {"type": "string"},
        }}}
    }
})
JUDGE_SCHEMA = strict_schema({
    "type": "object",
    "properties": {"claims": {"type": "array", "items": {"type": "object", "properties": {
        "id": {"type": "string"},
        "verdict": {"type": "string", "enum": ["confirmed", "partially_confirmed", "contradicted", "no_data"]},
        "explanation": {"type": "string"}, "evidence": {"type": "string"},
        "source_urls": {"type": "array", "items": {"type": "string"}},
    }}}}
})

EXTRACTION_SYSTEM = """Extract only concrete, factual claims that can be checked against public information. Never extract slogans, opinions, aspirations, generic descriptions, or marketing language.
Extract claims containing specific numbers, dates, named people or organizations, funding rounds, named investors/customers/competitors/partners, market size, or team history. Also extract internal traction metrics such as MRR, churn, and numbers of unnamed pilots or customers; mark these publicly_verifiable=false so the report shows them as not checked.
Examples to extract: 'Amenitiz raised €39M in a Series B in November 2025 led by KFund'; 'Backed by Seedcamp and K Fund'; 'Mews has raised less than $100M'; 'Spain has more than 14,000 hotels'; 'CEO Ana X previously founded Y'.
Examples NOT to extract: 'The operating system for independent hotels'; 'Stayflow brings guest operations into one workspace'; 'We are transforming hospitality'; 'A huge and growing market'.
Mark claims about third parties and public facts as publicly_verifiable=true even when the startup is unknown. Named investors, rounds, named customers, competitors, market facts, and team history are always publicly_verifiable=true. Internal metrics such as '€40k MRR' or '25 unnamed pilots' are still claims to extract, but set publicly_verifiable=false.
For every claim, write cala_question as a neutral search question that asks for the fact without assuming the claim is true and without asking for sources. Examples: 'How much total funding has Mews raised?'; 'Has Stayflow raised funding from Seedcamp or K Fund?'; 'How many hotels are there in Spain?'. Preserve the deck quote literally. Return only schema-compliant JSON."""

JUDGE_SYSTEM = """Judge each deck claim using only the supplied Cala evidence. If Cala finds no record or cannot find evidence/information, use no_data and explain that no record was found in Cala's sources and the founder should be asked for proof. Absence of evidence is never a contradiction. Use contradicted ONLY when Cala provides a concrete fact that conflicts with the claim, such as a different amount, date, investor, or figure. Use confirmed when the evidence establishes the same underlying fact, including harmless rounding or equivalent currency conversion (for example, €38.9M vs €39M for the same round/date); do not downgrade that to partially_confirmed. Use partially_confirmed only when one part of a multi-part claim is supported and another part is not established. Never infer support from irrelevant evidence. Return only schema-compliant JSON."""

PUBLIC_CATEGORIES = {"funding", "investor", "competitor", "customer", "partner", "market", "team"}
INTERNAL_METRIC_TERMS = ("mrr", "monthly recurring revenue", "churn", "unnamed pilot", "pilot hotels", "pilot customers")
NO_FINDING_PHRASES = ("unable to find", "no evidence", "no record", "could not find", "no information")


def guard_no_finding(verdict, evidence):
    """An absence-of-evidence statement cannot support a contradiction verdict."""
    if verdict == "contradicted" and any(phrase in (evidence or "").lower() for phrase in NO_FINDING_PHRASES):
        return "no_data"
    return verdict


def is_publicly_verifiable(claim):
    """Apply the invariant that third-party/public facts are queried, not skipped."""
    category = claim.get("category", "other")
    quote = claim.get("quote", "").lower()
    if category in PUBLIC_CATEGORIES:
        return True
    if any(term in quote for term in INTERNAL_METRIC_TERMS):
        return False
    return bool(claim.get("publicly_verifiable"))


async def _notify(callback, stage, done, total):
    if callback is None:
        return
    result = callback(stage, done, total)
    if inspect.isawaitable(result):
        await result


async def verify_pdf(path, provider=None, cala=None, llm=None, on_progress=None):
    started = time.monotonic()
    if llm is None:
        llm, model = make_llm(provider)
    elif isinstance(llm, tuple):
        llm, model = llm
    else:
        model = getattr(llm, "model", "custom")
    provider_name = provider or settings.llm_provider
    await _notify(on_progress, "extracting", 0, 0)
    pages = read_pdf(path)
    text = "\n\n".join(f"PAGE {p['page']}:\n{p['text']}" for p in pages)
    images = [p["image"] for p in pages] if provider_name == "nvidia" else None
    try:
        extraction = await llm.complete_json(EXTRACTION_SYSTEM, f"Extract at most 12 factual claims, prioritizing public claims.\n{text}", CLAIMS_SCHEMA, images)
    except Exception as exc:
        raise RuntimeError(f"Fallo en paso extract: {exc}") from exc
    claims = extraction.get("claims", [])[:12]
    for claim in claims:
        claim["publicly_verifiable"] = is_publicly_verifiable(claim)
    extract_s = time.monotonic() - started
    cala = cala or CalaClient(settings.cala_api_key, settings.cache_dir)
    check_start = time.monotonic()
    async def check(claim):
        if not claim.get("publicly_verifiable"):
            return claim, None
        try:
            return claim, await cala.search(claim["cala_question"])
        except Exception as exc:
            return claim, {"error": str(exc), "sources": [], "facts": [], "answer": ""}
    check_total = sum(c["publicly_verifiable"] for c in claims)
    await _notify(on_progress, "checking", 0, check_total)
    check_done = 0
    async def tracked_check(claim):
        nonlocal check_done
        result = await check(claim)
        if claim["publicly_verifiable"]:
            check_done += 1
            await _notify(on_progress, "checking", check_done, check_total)
        return result
    checked = await asyncio.gather(*(tracked_check(c) for c in claims))
    cala_s = time.monotonic() - check_start
    judge_start = time.monotonic()
    evidence_by_id = {c["id"]: {"claim": c, "cala": data} for c, data in checked}
    judge_claims = [c for c in claims if c["publicly_verifiable"]]
    batches = [judge_claims[i:i + 6] for i in range(0, len(judge_claims), 6)]
    batch_total = len(batches)
    await _notify(on_progress, "judging", 0, batch_total)
    batch_done = 0
    async def judge_batch(batch):
        nonlocal batch_done
        evidence = [evidence_by_id[c["id"]] for c in batch]
        prompt = "Judge only from Cala evidence. If evidence is absent or irrelevant, choose no_data. For each claim return id, verdict, explanation, short evidence quote, and source_urls.\n" + json.dumps(evidence, ensure_ascii=False)
        try:
            result = await llm.complete_json(JUDGE_SYSTEM, prompt, JUDGE_SCHEMA)
        except Exception as exc:
            raise RuntimeError(f"Fallo en paso judge (lote): {exc}") from exc
        batch_done += 1
        await _notify(on_progress, "judging", batch_done, batch_total)
        return result
    judged_batches = await asyncio.gather(*(judge_batch(batch) for batch in batches))
    judge_s = time.monotonic() - judge_start
    by_id = {item["id"]: item for batch in judged_batches for item in batch.get("claims", [])}
    checked_by_id = {c["id"]: data for c, data in checked}
    report_claims, dropped = [], 0
    counts = {key: 0 for key in ("confirmed", "partially_confirmed", "contradicted", "no_data", "not_checked")}
    score_points = 0
    for claim in claims:
        data, result = checked_by_id[claim["id"]], by_id.get(claim["id"], {})
        if not is_publicly_verifiable(claim):
            verdict = "not_checked"
            result = {"explanation": "Not publicly verifiable; skipped.", "evidence": "", "source_urls": []}
        elif data and data.get("error"):
            verdict = "error"
            result = {"explanation": data["error"], "evidence": "", "source_urls": []}
        else:
            original_verdict = result.get("verdict", "no_data")
            verdict = guard_no_finding(original_verdict, result.get("evidence", ""))
            if original_verdict == "contradicted" and verdict == "no_data":
                result = {**result, "explanation": "No record of this in Cala's sources; ask the founder for proof."}
        allowed = {s.get("url") for s in ((data or {}).get("sources") or []) if s.get("url")}
        urls = [u for u in result.get("source_urls", []) if u in allowed]
        dropped += len(result.get("source_urls", [])) - len(urls)
        if verdict in {"confirmed", "contradicted"} and not urls:
            verdict = "no_data"
        counts[verdict] = counts.get(verdict, 0) + 1
        score_points += {"confirmed": 1, "partially_confirmed": .5, "contradicted": -1}.get(verdict, 0)
        report_claims.append({**claim, "verdict": verdict, "explanation": result.get("explanation", ""), "evidence": result.get("evidence", ""), "sources": [s for s in ((data or {}).get("sources") or []) if s.get("url") in urls]})
    total_scored = sum(counts[k] for k in ("confirmed", "partially_confirmed", "contradicted"))
    score = round(max(0, min(100, 50 + 50 * score_points / total_scored))) if total_scored else 50
    return {"startup_name": extraction.get("startup_name", "Unknown"), "provider": provider_name, "model": model, "claims": report_claims, "summary": counts, "trust_score": score, "trust_score_formula": "clamp(50 + 50 × (confirmed + 0.5×partial − contradicted) / scored claims, 0, 100); 50 if none scored", "timings": {"extract_s":round(extract_s,2),"cala_s":round(cala_s,2),"judge_s":round(judge_s,2),"total_s":round(time.monotonic()-started,2)}, "dropped_urls": dropped, "scanned_pages_without_text": [p["page"] for p in pages if not p["text"]]}
