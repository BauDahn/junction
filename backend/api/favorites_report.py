"""PDF export for saved Cala entities."""
import asyncio
import html
import json
import re
from datetime import datetime
from io import BytesIO

import pymupdf as fitz


def build_plan_input(detail, profile, mode):
    facts = {key: detail.get(key) for key in
             ("name", "type", "description", "facts", "rounds", "people", "portfolio", "why_match", "score")}
    return json.dumps({"mode": mode, "cala_data": facts, "user_profile": profile or {}}, ensure_ascii=False, default=str)


async def action_plan(llm, detail, profile, mode):
    source = build_plan_input(detail, profile, mode)
    perspective = ("The user is a startup seeking investment and the entity is an investor to approach."
                   if mode == "raising" else "The user is an investor and the entity is a startup to evaluate.")
    system = ("Propose 3 to 5 concrete, actionable steps in English. Each step must be 1 or 2 sentences and anchored "
              "in a specific input fact, citing its name exactly as shown (for example, a portfolio company, a person "
              "and role, a lead investor, round type, sector, or why_match). " + perspective + " "
              "Never invent figures or names absent from the input. If user profile details such as sector, stage, "
              "ticket, or location are present, connect the step to them; otherwise do not invent a profile. "
              "Do not give generic steps such as reviewing a profile or monitoring activities without a concrete object. "
              "Return JSON matching the schema.")
    try:
        result = await asyncio.wait_for(llm.complete_json(
            system, source, {"type": "object", "properties": {"steps": {"type": "array", "items": {"type": "string"}}},
                            "required": ["steps"], "additionalProperties": False}), timeout=30)
        steps = result.get("steps", []) if isinstance(result, dict) else []
        input_numbers = set(re.findall(r"\d+", source))
        valid = [step.strip() for step in steps if isinstance(step, str) and step.strip()
                 and set(re.findall(r"\d+", step)) <= input_numbers]
        return valid[:5] if len(valid) >= 3 else None
    except Exception:
        return None


def _esc(value):
    return html.escape(str(value), quote=True)


def _source_catalog(detail):
    sources = []
    by_url = {}
    for key in ("facts", "rounds", "why_match"):
        for item in detail.get(key) or []:
            if not isinstance(item, dict):
                continue
            for source in item.get("sources") or []:
                if not isinstance(source, dict) or not source.get("url"):
                    continue
                url = str(source["url"])
                if url in by_url:
                    continue
                if len(sources) >= 30:
                    continue
                name = str(source.get("name") or url)
                if len(name) > 60:
                    name = name[:59].rstrip() + "…"
                record = {"url": url, "name": name, "date": source.get("date")}
                sources.append(record)
                by_url[url] = len(sources)
    return sources, by_url


def _render_rows(items, kind, by_url, sources):
    rows = []
    for item in items or []:
        if not isinstance(item, dict):
            if kind == "portfolio" and item:
                rows.append(f"<li>{_esc(item)}</li>")
            continue
        if kind == "data":
            text = f"{item.get('label') or ''}: {item.get('value') or ''}"
        elif kind == "rounds":
            text = _round_text(item, "")
        elif kind == "people":
            text = _esc(item.get("name") or "")
            if item.get("role"):
                text += " — " + _esc(item["role"])
            if item.get("since"):
                text += " (since " + _esc(item["since"]) + ")"
        elif kind == "portfolio":
            text = _esc(item.get("name") or "")
        else:
            text = _esc(item.get("text") or "")
        refs = []
        for source in item.get("sources") or []:
            if not isinstance(source, dict):
                continue
            number = by_url.get(str(source.get("url") or ""))
            if number and number not in refs:
                refs.append(number)
            if len(refs) == 3:
                break
        links = "".join(f'<a href="{_esc(sources[number - 1]["url"])}">[{number}]</a>' for number in refs)
        rows.append(f"<li>{text}{(' ' + links) if links else ''}</li>")
    return "".join(rows)


def _refs(item, by_url, sources):
    refs = []
    for source in item.get("sources") or []:
        if not isinstance(source, dict):
            continue
        number = by_url.get(str(source.get("url") or ""))
        if number and number not in refs:
            refs.append(number)
        if len(refs) == 3:
            break
    return "".join(f'<a href="{_esc(sources[number - 1]["url"])}">[{number}]</a>' for number in refs)


def _round_text(item, entity_name):
    own_name = str(entity_name or "").casefold()
    leads = [str(name) for name in (item.get("leads") or []) if str(name).casefold() != own_name]
    investors = [str(name) for name in (item.get("investors") or []) if str(name).casefold() != own_name]
    parts = [item.get("round_type"), item.get("amount"), item.get("date")]
    text = " · ".join(_esc(part) for part in parts if part not in (None, ""))
    if leads:
        text += (" · " if text else "") + "Leads: " + _esc(", ".join(leads))
    if investors:
        text += (" · " if text else "") + "Investors: " + _esc(", ".join(investors))
    return text


def _round_rows(items, entity_name, by_url, sources):
    detailed, private = [], []
    for item in items or []:
        if not isinstance(item, dict):
            continue
        text = _round_text(item, entity_name)
        if text:
            detailed.append((item, text))
        else:
            private.append(item)
    detailed.sort(key=lambda pair: str(pair[0].get("date") or ""), reverse=True)
    rows = []
    for item, text in detailed[:8]:
        refs = _refs(item, by_url, sources)
        rows.append(f'<li>{text}{(" " + refs) if refs else ""}</li>')
    if len(detailed) > 8:
        rows.append(f"<li>and {len(detailed) - 8} more</li>")
    if private:
        refs = []
        for item in private:
            for source in item.get("sources") or []:
                if isinstance(source, dict):
                    number = by_url.get(str(source.get("url") or ""))
                    if number and number not in refs:
                        refs.append(number)
                    if len(refs) == 3:
                        break
            if len(refs) == 3:
                break
        links = "".join(f'<a href="{_esc(sources[number - 1]["url"])}">[{number}]</a>' for number in refs)
        rows.append(f'<li>{len(private)} more rounds on record in Cala without public details{(" " + links) if links else ""}</li>')
    return "".join(rows)


def _limited_rows(items, kind, by_url, sources, limit):
    items = list(items or [])
    visible = _render_rows(items[:limit], kind, by_url, sources)
    remainder = len(items) - limit
    if remainder > 0:
        visible += f"<li>and {remainder} more</li>"
    return visible


def _date_label(generated_at):
    try:
        value = generated_at if isinstance(generated_at, datetime) else datetime.fromisoformat(str(generated_at).replace("Z", "+00:00"))
        return value.strftime("%-d %B %Y")
    except (ValueError, TypeError):
        return str(generated_at)


def _source_list(sources):
    rows = []
    for number, source in enumerate(sources, 1):
        url = _esc(source["url"])
        date = f' ({_esc(_date_label(source["date"]))})' if source.get("date") else ""
        rows.append(f'<li><a href="{url}">[{number}] {_esc(source["name"])} — {url}</a>{date}</li>')
    return "".join(rows)


def render_pdf(entries, not_included, mode, generated_at):
    stamp = _date_label(generated_at)
    mode_label = {"raising": "Raising (investors to approach)", "investing": "Investing (startups to back)"}.get(mode, mode)
    cover_entities = []
    for entry in entries:
        detail = entry["detail"]
        score = f' · Score: {_esc(detail["score"])}' if detail.get("score") is not None else ""
        cover_entities.append(f'<li>{_esc(detail.get("name") or "Not available in Cala")} · {_esc(detail.get("type") or "Not available in Cala")}{score}</li>')
    cover_missing = [f'<li>{_esc(row["id"])}: {_esc(row["reason"])}</li>' for row in not_included or []]
    cover = (f"<h1>Cala Match</h1><h2>Favorites report</h2><p>{_esc(stamp)}</p><p>Mode: {_esc(mode_label)}</p>"
             f"<ul>{''.join(cover_entities)}</ul><p>Facts come from Cala, each with its numbered source. Action plans are generated by Gemini from those facts and labeled as such.</p>")
    if cover_missing:
        cover += f'<h3>Not included</h3><ul>{"".join(cover_missing)}</ul>'
    pages = [cover]
    for entry in entries:
        d = entry["detail"]
        sources, by_url = _source_catalog(d)
        sections = []
        for title, key, kind in (("Data", "facts", "data"), ("Rounds", "rounds", "rounds"),
                                 ("People", "people", "people"), ("Portfolio", "portfolio", "portfolio"),
                                 ("Why it matches", "why_match", "why")):
            items = d.get(key) or []
            if kind == "rounds":
                content = _round_rows(items, d.get("name"), by_url, sources)
            elif kind == "people":
                content = _limited_rows(items, kind, by_url, sources, 12)
            elif kind == "portfolio":
                content = _limited_rows(items, kind, by_url, sources, 12)
            else:
                content = _render_rows(items, kind, by_url, sources)
            if content:
                sections.append(f"<h3>{title}</h3><ul>{content}</ul>")
        score = f'<p>Score: {_esc(d["score"])}</p>' if d.get("score") is not None else ""
        desc = f'<p>{_esc(d["description"])}</p>' if d.get("description") else ""
        plan = "<p>Action plan unavailable</p>" if not entry.get("plan") else "<ol>" + "".join(f"<li>{_esc(s)}</li>" for s in entry["plan"]) + "</ol>"
        source_content = f'<ul>{_source_list(sources)}</ul>' if sources else "Not available in Cala"
        pages.append(f'<h1>{_esc(d.get("name") or "Not available in Cala")}</h1><p>Type: {_esc(d.get("type") or "Not available in Cala")}</p>{score}{desc}{"".join(sections)}<h3>Cala sources</h3>{source_content}<div class="plan"><h2>Proposed action plan</h2><p>Generated by Gemini from the Cala data above. Not Cala data.</p>{plan}</div>')
    css = "body{font:10pt sans-serif;color:#17202a}h1{color:#006cbd}h2{color:#244}li{margin:4pt 0}.plan{border:1px solid #789;background:#eef4fa;padding:10pt;margin-top:18pt}a{color:#0563c1}"
    out = BytesIO()
    writer = fitz.DocumentWriter(out)
    for index, content in enumerate(pages):
        story = fitz.Story(f'<html><head><style>{css}</style></head><body>{content}</body></html>')
        rect = fitz.Rect(48, 48, 548, 770)
        more = True
        while more:
            page = fitz.Rect(0, 0, 595, 842)
            device = writer.begin_page(page)
            more, filled = story.place(rect)
            story.draw(device)
            writer.end_page()
    writer.close()
    document = fitz.open(stream=out.getvalue(), filetype="pdf")
    for page_number, page in enumerate(document, 1):
        page.insert_text((48, 812), f"Data: Cala · Plan: Gemini                         Page {page_number}", fontsize=8)
    return document.tobytes()
