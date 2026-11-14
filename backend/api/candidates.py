"""Construcción rápida del feed sobre datos locales."""
import time
from .affinity import score_candidate, rank, parse_amount

_BFS={}
def _uniq(vals):return list(dict.fromkeys(str(v).strip() for v in vals if v is not None and str(v).strip()))
def normalize_profile(p,mode,seeds):
    p=p or {}; interests=p.get('interests') or {}; raising=p.get('raising') or {}; sec=interests.get('sectors') or []
    understood=p.get('what_we_understood') or {}; focus=understood.get('sector_focus')
    if (sec==['other'] or not sec) and focus: sec=[focus]
    sector=_uniq(([p.get('sector')] if p.get('sector') else [])+sec)
    loc=_uniq(([p.get('location')] if p.get('location') else [])+(interests.get('regions') or []))
    if mode=='raising':
        stages=_uniq([raising.get('round') or p.get('stage')]); ticket=p.get('ticket_range')
        if isinstance(ticket,dict) and (ticket.get('min') is not None or ticket.get('max') is not None): t={'min':ticket.get('min'),'max':ticket.get('max')}
        else:
            amount=parse_amount(raising.get('amount')); t={'min':amount,'max':amount} if amount is not None else None
    else:
        stages=_uniq((interests.get('stages') or [])+([p.get('stage')] if p.get('stage') else [])); t=None
    return {'sectors':sector,'stage':stages[0] if stages else None,'stages':stages,'regions':loc,'ticket':t,'seeds':list(seeds or [])}
def seed_names(p):
    i=(p or {}).get('interests') or {}; f=i.get('follows') or {}
    return _uniq(([p.get('startup_name')] if p.get('startup_name') else [])+(p.get('competitors') or [])+(f.get('companies') or [])+(f.get('investors') or []))
def _bfs(session,seed_ids,store):
    key=(session,tuple(sorted(seed_ids))); now=time.monotonic(); cached=_BFS.get(key)
    if cached and now-cached[0]<30:return cached[1]
    dist={i:(0,[]) for i in seed_ids}; frontier=list(seed_ids)
    for depth in range(1,4):
        batch=store.neighbors(frontier)
        nxt=[]
        for i in frontier:
            for edge,node in batch.get(str(i),[]):
                sources=edge.get('sources') or []
                if not sources:continue
                j=str(node.get('id'))
                if j not in dist:dist[j]=(depth,sources);nxt.append(j)
        frontier=nxt
        if not frontier:break
    _BFS[key]=(now,dist);return dist
def build_feed(session_id,profile,mode,catalog,store,today=None):
    seeds=store.view_seeds(session_id) or [store.resolve(n) for n in seed_names(profile)]; seeds=[str(s) for s in seeds if s]
    dist=_bfs(session_id,seeds,store) if seeds else {}
    kind='investor' if mode=='raising' else 'startup'; features=catalog.list_features(kind); seen=set(); candidates=[]
    for f in features:
        if f['id'] in seeds:continue
        seen.add(f['id']); d=dist.get(f['id']); candidates.append({'id':f['id'],'name':f['name'],'type':kind,'rounds':f.get('rounds') or _enriched.get(f['id'],[]),'attrs':{'industries':f.get('sectors',[]),'hq':f.get('hq'),'country':f.get('country'),'ai_tagged':f.get('ai_tagged'),'sources':f.get('sources',[])},'features':{'stages':f.get('stages',[]),'amount':f.get('amount',{}),'activity':f.get('activity',{}),'sources':f.get('sources',[])},'distance':d[0] if d else None,'distance_sources':d[1] if d else []})
    for ident,(distance,sources) in dist.items():
        if ident in seen or ident in seeds:continue
        node=store.get_node(ident)
        if not node:continue
        edges=store.edges_of(ident); outgoing=any(e.get('rel')=='INVESTED_IN' and str(e.get('src'))==ident and e.get('sources') for e in edges); incoming=any(e.get('rel')=='INVESTED_IN' and str(e.get('dst'))==ident and e.get('sources') for e in edges)
        if not (outgoing if kind=='investor' else incoming):continue
        props=node.get('props') or {}; ns=props.get('sources') or node.get('sources') or []; attrs={'industries':props.get('industries',[]) if ns else [],'hq':props.get('hq') if ns else None,'country':props.get('country') if ns else None,'sources':ns}
        candidates.append({'id':ident,'name':node.get('name'),'type':kind,'rounds':_enriched.get(ident,[]),'attrs':attrs,'distance':distance,'distance_sources':sources})
    p=normalize_profile(profile,mode,seeds); results=[]
    for c in candidates:results.append(score_candidate(p,c,today=today)|{'_candidate':c})
    ordered=rank(results)
    status=catalog.status(); notes=[]
    if len(features)==0 or status and status.get('done',0)<status.get('total',0):notes.append(f"Catalog is still loading: {status.get('done',0)} of {status.get('total',0)} profiled." if status else "Catalog is still loading.")
    if not any([p['sectors'],p['stage'],p['regions'],p['ticket']]):notes.append('Add your sector, stage and region to get better matches.')
    if not seeds:notes.append('Your company is not in the graph yet: matches use your profile only.')
    return {'results':ordered,'note':' '.join(notes) or None}
_enriched={}
def set_enriched(ident,rounds):_enriched[ident]=rounds
