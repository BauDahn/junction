"""PDF export for saved Cala entities."""
import asyncio
import html
import json
import re
from datetime import datetime
from io import BytesIO
from urllib.parse import urlsplit

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
                normalized = _normalize_source(source)
                if not normalized:
                    continue
                url = normalized["url"]
                if url in by_url:
                    continue
                if len(sources) >= 30:
                    continue
                name = normalized["name"]
                if len(name) > 60:
                    name = name[:59].rstrip() + "…"
                record = {"url": url, "name": name, "date": normalized["date"]}
                sources.append(record)
                by_url[url] = len(sources)
    return sources, by_url


def _normalize_source(source):
    if not isinstance(source, dict):
        return None
    url = source.get("document") or source.get("url")
    if not url:
        return None
    url = str(url)
    host = urlsplit(url).hostname or url
    return {"url": url, "name": str(source.get("name") or host), "date": source.get("date")}


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
        refs = _reference_numbers([item], by_url)
        links = "".join(f'<a href="{_esc(sources[number - 1]["url"])}">[{number}]</a>' for number in refs)
        rows.append(f"<li>{text}{(' ' + links) if links else ''}</li>")
    return "".join(rows)


def _reference_numbers(items, by_url):
    refs = []
    for item in items:
        for source in item.get("sources") or []:
            normalized = _normalize_source(source)
            if not normalized:
                continue
            number = by_url.get(normalized["url"])
            if number and number not in refs:
                refs.append(number)
            if len(refs) == 3:
                return refs
    return refs


def _refs(item, by_url, sources):
    refs = _reference_numbers([item], by_url)
    return "".join(f'<a href="{_esc(sources[number - 1]["url"])}">[{number}]</a>' for number in refs)


def _round_text(item, entity_name):
    own_name = str(entity_name or "").casefold()
    leads = [str(name) for name in (item.get("leads") or []) if str(name).casefold() != own_name]
    investors = [str(name) for name in (item.get("investors") or []) if str(name).casefold() != own_name]
    if not (item.get("round_type") or item.get("amount") or leads or investors):
        return ""
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
        years = {}
        for item in private:
            date = str(item.get("date") or "")
            year_match = re.match(r"^(\d{4})", date)
            if year_match:
                year = year_match.group(1)
                years[year] = years.get(year, 0) + 1
        refs = _reference_numbers(private, by_url)
        links = "".join(f'<a href="{_esc(sources[number - 1]["url"])}">[{number}]</a>' for number in refs)
        years_text = ", ".join(f"{count} dated {year}" for year, count in sorted(years.items(), reverse=True))
        date_summary = f" ({_esc(years_text)})" if years_text else ""
        noun = "round" if len(private) == 1 else "rounds"
        rows.append(f'<li>{len(private)} {noun} on record in Cala{date_summary}, without public details{(" " + links) if links else ""}</li>')
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


def render_pdf(entries, not_included, mode, generated_at, profile=None):
    stamp = _date_label(generated_at)
    mode_label = {"raising": "Raising (investors to approach)", "investing": "Investing (startups to back)"}.get(mode, mode)
    catalogs = [_source_catalog(entry["detail"]) for entry in entries]
    def refs(item, by_url, sources):
        return " ".join(f'<a href="{_esc(sources[n - 1]["url"])}">[{n}]</a>' for n in _reference_numbers([item], by_url))
    def table(headers, rows):
        return '<table><thead><tr>' + ''.join(f'<th>{h}</th>' for h in headers) + '</tr></thead><tbody>' + ''.join('<tr>'+''.join(f'<td>{c}</td>' for c in row)+'</tr>' for row in rows) + '</tbody></table>'
    def list_rows(items, kind, by_url, sources, limit=10):
        rendered = []
        for item in (items or [])[:limit]:
            if isinstance(item, dict):
                name = _esc(item.get('name') or item.get('text') or '')
                if kind == 'people' and item.get('role'):
                    name += ' — ' + _esc(item['role'])
                rendered.append(f'<li>{name} {refs(item, by_url, sources)}</li>')
            elif item:
                rendered.append(f'<li>{_esc(item)}</li>')
        if len(items or []) > limit:
            rendered.append(f'<li>and {len(items)-limit} more</li>')
        return '<ul>'+''.join(rendered)+'</ul>' if rendered else '<p>Not available in Cala</p>'
    cover_rows=[]
    for index, entry in enumerate(entries):
        d=entry['detail']; why=(d.get('why_match') or [])
        reason=why[0].get('text','') if why and isinstance(why[0],dict) else ''
        cover_rows.append([_esc(d.get('name') or 'Not available in Cala'), _esc(d.get('type') or 'Not available in Cala'),
                           _esc(d.get('score') if d.get('score') is not None else '—'), _esc(reason or '—'), str(index+2)])
    profile_name = (profile or {}).get('company') or (profile or {}).get('startup') or (profile or {}).get('fund') or (profile or {}).get('name')
    cover=f'<h1>Favorites report</h1><p>{_esc(stamp)} · Mode: {_esc(mode_label)}</p>'
    if profile_name: cover+=f'<p>Profile: {_esc(profile_name)}</p>'
    cover+='<h2>Summary</h2>'+table(['Name','Type','Match','Why it matches','Page'],cover_rows)
    cover+='<p class="note">Each numbered reference links to its Cala source. Missing information is marked when Cala has no data; Gemini plans use only the Cala data shown.</p>'
    if not_included:
        cover+='<h3>Not included</h3><ul>'+''.join(f'<li>{_esc(x["id"])}: {_esc(x["reason"])}</li>' for x in not_included)+'</ul>'
    stories=[cover]
    for entry,(sources,by_url) in zip(entries,catalogs):
        d=entry['detail']; name=d.get('name') or 'Not available in Cala'; score=d.get('score')
        confidence=d.get('confidence'); empty=not any(d.get(k) for k in ('description','facts','rounds','people','portfolio','why_match'))
        html_body=f'<div class="entity"><div class="band"><div><h1>{_esc(name)}</h1><p>{_esc(d.get("type") or "Not available in Cala")}</p></div><div class="match">Match {_esc(score if score is not None else "—")}</div></div>'
        if confidence is not None and confidence < .5: html_body+='<p class="partial">Partial data</p>'
        if d.get('description'): html_body+=f'<p class="description">{_esc(d["description"])}</p>'
        if empty: html_body+='<p>No data available in Cala.</p><p>What was tried: '+_esc(d.get('attempted') or d.get('query') or name)+'</p>'
        else:
            facts=[]
            for fact in d.get('facts') or []:
                if isinstance(fact,dict): facts.append([_esc(fact.get('label') or '—'),_esc(fact.get('value') or '—')+' '+refs(fact,by_url,sources)])
            if facts: html_body+='<h2>At a glance</h2>'+table(['Field','Value'],facts)
            reasons=[f'<li>{_esc(x.get("text") or "")} {refs(x,by_url,sources)}</li>' for x in d.get('why_match') or [] if isinstance(x,dict)]
            if reasons: html_body+='<h2>Why it matches</h2><ul>'+''.join(reasons)+'</ul>'
            rounds=[]
            all_rounds=[]; private_rounds=[]
            for x in d.get('rounds') or []:
                if not isinstance(x,dict): continue
                own=str(name).casefold()
                leads=[str(v) for v in (x.get('leads') or []) if str(v).casefold()!=own]
                investors=[str(v) for v in (x.get('investors') or []) if str(v).casefold()!=own]
                if not (x.get('round_type') or x.get('amount') or leads or investors):
                    private_rounds.append(x); continue
                all_rounds.append((x,[ _esc(x.get('date') or '—'),_esc(x.get('round_type') or '—'),_esc(x.get('amount') or '—'),_esc(', '.join(leads) or '—'),_esc(', '.join(investors) or '—')+' '+refs(x,by_url,sources)]))
            all_rounds.sort(key=lambda pair:str(pair[0].get('date') or ''),reverse=True)
            rounds=[row for _,row in all_rounds[:8]]
            if len(all_rounds)>8: rounds.append([f'and {len(all_rounds)-8} more','','','',''])
            if private_rounds:
                rounds.append([f'{len(private_rounds)} round(s) on record in Cala, without public details','','','',refs(private_rounds[0],by_url,sources)])
            html_body+='<h2>Funding rounds</h2>'+ (table(['Date','Round','Amount','Lead investors','Other investors'],rounds) if rounds else '<p>No detailed funding round data available in Cala.</p>')
            html_body+='<table class="columns"><tbody><tr><td><h2>Portfolio</h2>'+list_rows(d.get('portfolio'), 'portfolio',by_url,sources)+'</td><td><h2>People</h2>'+list_rows(d.get('people'),'people',by_url,sources)+'</td></tr></tbody></table>'
        plan='<ol>'+''.join(f'<li>{_esc(s)}</li>' for s in entry.get('plan') or [])+'</ol>' if entry.get('plan') else '<p>Action plan unavailable</p>'
        html_body+='<div class="plan"><h2>Proposed action plan</h2><p>Generated by Gemini from the Cala data above. Not Cala data.</p>'+plan+'</div>'
        if sources:
            srcrows=[]
            for n,s in enumerate(sources,1):
                host=urlsplit(s['url']).hostname or s['url']; label=s.get('name') or host
                date=' — '+_esc(_date_label(s['date'])) if s.get('date') else ''
                srcrows.append(f'<li><a href="{_esc(s["url"])}">[{n}] {_esc(label if label != host else host)}{date}</a></li>')
            html_body+='<h2>Sources</h2><ol class="sources">'+''.join(srcrows)+'</ol>'
        else: html_body+='<h2>Sources</h2><p>Not available in Cala</p>'
        html_body+='</div>'; stories.append(html_body)
    css='''@page{size:A4;margin:18mm} body{font:9pt Helvetica,sans-serif;color:#0B1C30} h1{font-size:24pt;margin:0 0 8pt;color:#0B1C30} h2{font-size:13pt;margin:13pt 0 5pt;page-break-after:avoid} h3{font-size:10pt;page-break-after:avoid} p{margin:4pt 0 8pt} a{color:#006CFF;text-decoration:none} table{width:100%;border-collapse:collapse;margin:4pt 0 10pt} thead{display:table-header-group} th{text-align:left;background:#F1F4F8} th,td{border-bottom:.5pt solid #D9DEE8;padding:5pt 4pt;vertical-align:top} tr{page-break-inside:avoid} ul,ol{padding-left:18pt;margin:4pt 0 9pt} li{margin:3pt 0} .band{display:flex;justify-content:space-between;align-items:center;border-bottom:1pt solid #D9DEE8;padding-bottom:8pt}.band h1{font-size:22pt}.band p,.partial{color:#5B6472}.match{border:1pt solid #D9DEE8;padding:10pt;font-size:13pt}.description{color:#5B6472}.columns{display:flex;gap:20pt}.columns section{width:50%}.plan{background:#F1F6FF;border:1pt solid #D9DEE8;padding:8pt;margin:10pt 0}.plan h2{margin-top:0}.sources{font-size:8pt;columns:2}.note{color:#5B6472;margin-top:14pt}'''
    content=fitz.Rect(51,51,544,785)
    def page_count(body):
        probe=fitz.Story(f'<html><head><style>{css}</style></head><body>{body}</body></html>')
        counter=fitz.DocumentWriter(BytesIO()); page_rect=fitz.Rect(0,0,595,842); count=0
        while True:
            device=counter.begin_page(page_rect); more,_=probe.place(content); probe.draw(device); counter.end_page(); count+=1
            if not more: return count
    page_number=page_count(cover)
    corrected=[]
    for row,entity_body in zip(cover_rows,stories[1:]):
        page_number+=1; fixed=list(row); fixed[-1]=str(page_number); corrected.append(fixed)
        page_number+=page_count(entity_body)-1
    if corrected:
        cover=cover.replace(table(['Name','Type','Match','Why it matches','Page'],cover_rows),
                            table(['Name','Type','Match','Why it matches','Page'],corrected))
        stories[0]=cover
    out=BytesIO(); writer=fitz.DocumentWriter(out); page_rect=fitz.Rect(0,0,595,842)
    for body in stories:
        story=fitz.Story(f'<html><head><style>{css}</style></head><body>{body}</body></html>')
        while True:
            device=writer.begin_page(page_rect); more,_=story.place(content); story.draw(device); writer.end_page()
            if not more: break
    writer.close(); doc=fitz.open(stream=out.getvalue(),filetype='pdf'); total=len(doc)
    for n,page in enumerate(doc,1):
        page.insert_text((51,24),'calado · Favorites report',fontsize=8,fontname='helv',color=(0,0.424,1))
        page.insert_text((51,823),'Data: Cala · Action plans: Gemini',fontsize=8,fontname='helv',color=(.35,.39,.45))
        page.insert_text((440,823),f'Page {n} of {total}',fontsize=8,fontname='helv',color=(.35,.39,.45))
    # DocumentWriter currently drops HTML link annotations, so restore links on
    # the compact source titles after layout, where their final positions are known.
    for sources,_ in catalogs:
        for number,source in enumerate(sources,1):
            linked=False
            for page in doc:
                heads=page.search_for('Sources')
                markers=[rect for rect in page.search_for(f'[{number}]') if heads and rect.y0 > heads[0].y0]
                if markers:
                    page.insert_link({'kind':fitz.LINK_URI,'from':markers[-1],'uri':source['url']})
                    linked=True
            if not linked:
                label=source.get('name') or (urlsplit(source['url']).hostname or source['url'])
                for page in doc:
                    matches=page.search_for(label)
                    if matches:
                        page.insert_link({'kind':fitz.LINK_URI,'from':matches[-1],'uri':source['url']})
                        break
    return doc.tobytes()
