"""PDF export for saved Cala entities."""
import asyncio
import html
import json
import re
from datetime import datetime
from io import BytesIO

import pymupdf as fitz


def build_plan_input(detail, profile):
    facts = {key: detail.get(key) for key in
             ("name", "type", "description", "facts", "rounds", "people", "portfolio", "why_match", "score")}
    return json.dumps({"cala_data": facts, "user_profile": profile or {}}, ensure_ascii=False, default=str)


async def action_plan(llm, detail, profile):
    source = build_plan_input(detail, profile)
    system = ("Propose 3 to 5 concrete action steps in English using only the information in the input. "
              "Never invent figures, names, dates, or facts. If the input is sparse, suggest generic process steps "
              "without figures. Return JSON matching the schema.")
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


def _source_links(sources):
    return " · ".join(f'<a href="{_esc(s.get("url") or "#")}">{_esc(s.get("name") or s.get("url") or "Source")}</a>'
                      for s in (sources or []) if isinstance(s, dict))


def _render_rows(items, kind):
    rows = []
    for item in items or []:
        if not isinstance(item, dict):
            if kind == "portfolio" and item:
                rows.append(f"<li>{_esc(item)}</li>")
            continue
        if kind == "data":
            text = f"{item.get('label') or ''}: {item.get('value') or ''}"
        elif kind == "rounds":
            parts = [item.get("round_type"), item.get("amount"), item.get("date")]
            text = " · ".join(_esc(part) for part in parts if part not in (None, ""))
            if item.get("leads"):
                text += (" · " if text else "") + "Leads: " + _esc(", ".join(map(str, item["leads"])))
            if item.get("investors"):
                text += (" · " if text else "") + "Investors: " + _esc(", ".join(map(str, item["investors"])))
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
        sources = _source_links(item.get("sources"))
        rows.append(f"<li>{text}{(' · ' + sources) if sources else ''}</li>")
    return "".join(rows)


def _date_label(generated_at):
    try:
        value = generated_at if isinstance(generated_at, datetime) else datetime.fromisoformat(str(generated_at).replace("Z", "+00:00"))
        return value.strftime("%-d %B %Y")
    except (ValueError, TypeError):
        return str(generated_at)


def _all_sources(detail):
    sources = []
    seen = set()
    for key in ("facts", "rounds", "people", "portfolio", "why_match"):
        for item in detail.get(key) or []:
            if isinstance(item, dict):
                for source in item.get("sources") or []:
                    if not isinstance(source, dict):
                        continue
                    url = source.get("url")
                    if not url or url in seen:
                        continue
                    seen.add(url)
                    name = source.get("name") or url
                    link = f'<a href="{_esc(url)}">{_esc(name)}</a>'
                    date = f' ({_esc(_date_label(source["date"]))})' if source.get("date") else ""
                    sources.append(link + date)
    return " · ".join(sources)


def render_pdf(entries, not_included, mode, generated_at):
    stamp = _date_label(generated_at)
    mode_label = {"raising": "Raising (investors to approach)", "investing": "Investing (startups to back)"}.get(mode, mode)
    pages = [f"<h1>Cala Match</h1><h2>Favorites report</h2><p>{_esc(stamp)}</p><p>Mode: {_esc(mode_label)}</p>"]
    for entry in entries:
        d = entry["detail"]
        sections = []
        for title, key, kind in (("Data", "facts", "data"), ("Rounds", "rounds", "rounds"),
                                 ("People", "people", "people"), ("Portfolio", "portfolio", "portfolio"),
                                 ("Why it matches", "why_match", "why")):
            items = d.get(key) or []
            content = _render_rows(items, kind)
            if content:
                sections.append(f"<h3>{title}</h3><ul>{content}</ul>")
        score = f'<p>Score: {_esc(d["score"])}</p>' if d.get("score") is not None else ""
        desc = f'<p>{_esc(d["description"])}</p>' if d.get("description") else ""
        plan = "<p>Action plan unavailable</p>" if not entry.get("plan") else "<ol>" + "".join(f"<li>{_esc(s)}</li>" for s in entry["plan"]) + "</ol>"
        pages.append(f'<h1>{_esc(d.get("name") or "Not available in Cala")}</h1><p>Type: {_esc(d.get("type") or "Not available in Cala")}</p>{score}{desc}{"".join(sections)}<h3>Cala sources</h3><p>{_all_sources(d) or "Not available in Cala"}</p><div class="plan"><h2>Proposed action plan</h2><p>Generated by Gemini from the Cala data above. Not Cala data.</p>{plan}</div>')
    if not_included:
        pages.append('<h1>Not included</h1><ul>' + "".join(f'<li>{_esc(row["id"])}: {_esc(row["reason"])}</li>' for row in not_included) + "</ul>")
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
