"""Endpoints del feed y detalle de Cala Match."""
import asyncio, base64, json, os
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from chat import store as chat_store
from .catalog_port import get_catalog
from .graph_port import get_graph
from .candidates import build_feed, normalize_profile, seed_names, set_enriched
from .affinity import score_candidate, rank
router=APIRouter(); _tasks=set(); _failed=set(); _active=set(); _cala=None

def get_cala():
    global _cala
    if _cala is None:
        try:
            from canonizador.client import CalaClient
            from verifier.config import settings
            if not settings.cala_api_key:return None
            _cala=CalaClient(settings.cala_api_key,settings.cache_dir)
        except Exception:return None
    return _cala
def _session(sid):
    if not chat_store.session_exists(sid):raise HTTPException(404,'Session not found.')
def _mode(mode,sid=None):
    m=mode or (chat_store.get_mode(sid) if sid else None) or 'raising'
    if m not in ('raising','investing'):raise HTTPException(422,'Mode must be raising or investing.')
    return m
def _src(src):return src if isinstance(src,list) else []
def _union(*groups,limit=8):
    out=[]; seen=set()
    for group in groups:
        for s in group or []:
            if not isinstance(s,dict):continue
            k=s.get('url') or s.get('name') or json.dumps(s,sort_keys=True)
            if k not in seen:seen.add(k);out.append(s)
            if len(out)>=limit:return out
    return out
def _feedcard(r):
    c=r['_candidate']; f=c.get('_features') or {}; sources=c.get('attrs',{}).get('sources',[]); tags=[]
    ai=f.get('ai_tagged',False)
    for x in (f.get('sectors',[])[:2] if f.get('sources') else []):tags.append(str(x)+(' (AI-tagged)' if ai is True or isinstance(ai,list) and 'sectors' in ai else ''))
    if f.get('stages') and f.get('sources'):
        x=f['stages'][0];tags.append(str(x)+(' (AI-tagged)' if ai is True or isinstance(ai,list) and 'stages' in ai else ''))
    if f.get('country') and f.get('sources'):tags.append(f['country'])
    why=r.get('why_match',[])
    return {'id':r['id'],'type':r['type'],'name':r['name'],'one_liner':(f.get('description') or '')[:160].rsplit(' ',1)[0] if f.get('description') and sources and len(f['description'])>160 else f.get('description','') if sources else '', 'tags':tags,'score':r['score'],'confidence':r['confidence'],'why_match':[s['text'] for s in why],'sources':_union(sources,*(s['sources'] for s in why))}
def _cursor(item):return base64.urlsafe_b64encode(json.dumps([item['score'],item['confidence'],item['name'].casefold(),str(item['id'])],separators=(',',':')).encode()).decode().rstrip('=')
def _key(item):return (-item['score'],-item['confidence'],item['name'].casefold(),str(item['id']))
@router.get('/api/feed')
async def feed(session_id:str=Query(...),mode:str|None=None,limit:int=Query(20,ge=1,le=100),cursor:str|None=None,catalog=Depends(get_catalog),graph=Depends(get_graph)):
    _session(session_id); mode=_mode(mode,session_id); profile=chat_store.get_profile(session_id) or {}
    result=await asyncio.to_thread(build_feed,session_id,profile,mode,catalog,graph); rows=result['results']; cards=[]
    for row in rows:
        row['_candidate']['_features']=catalog.get_features(row['id']) or {}
        cards.append(_feedcard(row))
    if mode=='raising':_schedule_enrich(cards,catalog)
    if cursor:
        try:
            raw=base64.urlsafe_b64decode(cursor+'='*((4-len(cursor)%4)%4)); vals=json.loads(raw)
            if not isinstance(vals,list) or len(vals)!=4:raise ValueError()
            key=(-int(vals[0]),-float(vals[1]),str(vals[2]),str(vals[3])); cards=[x for x in cards if _key(x)>key]
        except Exception:raise HTTPException(422,'Invalid cursor.')
    page=cards[:limit]; out={'mode':mode,'items':page}
    if len(cards)>limit:out['next_cursor']=_cursor(page[-1])
    if result['note']:out['confidence_note']=result['note']
    return out
def _schedule_enrich(cards,catalog):
    try:n=int(os.getenv('FEED_ENRICH_TOP','0'))
    except ValueError:n=0
    cala=get_cala() if n>0 else None
    if not cala:return
    from .profiles import investor_rounds
    for card in cards:
        if n<=0:break
        ident=card['id']
        if catalog.get_features(ident) and catalog.get_features(ident).get('rounds') or ident in _enriched_ids():continue
        if ident in _active or ident in _failed:continue
        _active.add(ident);n-=1
        async def run(i=ident,name=card['name']):
            try:
                result=await investor_rounds(cala,name);set_enriched(i,result.get('rounds',[]))
            except Exception:_failed.add(i)
            finally:_active.discard(i)
        t=asyncio.create_task(run());_tasks.add(t);t.add_done_callback(_tasks.discard)
def _enriched_ids():
    from . import candidates
    return set(candidates._enriched)
@router.get('/api/entities/{entity_id}')
async def entity(entity_id:str,mode:str|None=None,session_id:str|None=None,catalog=Depends(get_catalog),graph=Depends(get_graph)):
    if mode is not None:mode=_mode(mode,session_id)
    elif session_id:mode=_mode(None,session_id)
    else:mode='raising'
    feat=await asyncio.to_thread(catalog.get_features,entity_id); node=graph.get_node(entity_id)
    if not feat and not node:raise HTTPException(404,'Entity not found.')
    edges=graph.neighbors([entity_id]).get(entity_id,[]); kinds=feat.get('kinds',[]) if feat else []
    invedge=any(e.get('rel')=='INVESTED_IN' and str(e.get('src'))==entity_id for e,n in edges); startupedge=any(e.get('rel')=='INVESTED_IN' and str(e.get('dst'))==entity_id for e,n in edges)
    typ=('investor' if mode=='raising' else 'startup') if 'investor' in kinds and 'startup' in kinds else next((k for k in ('investor','startup') if k in kinds),None) or ('investor' if invedge else 'startup')
    src=feat.get('sources',[]) if feat else []; props=node.get('props',{}) if node else {}; nsrc=props.get('sources') or node.get('sources',[]) if node else []; allsrc=src or nsrc
    out={'id':entity_id,'type':typ,'name':feat.get('name') if feat else node.get('name'),'why_match':[],'facts':[],'rounds':[],'portfolio':[],'people':[],'loaded_at':feat.get('loaded_at') if feat else node.get('loaded_at')}
    desc=(feat.get('description') if feat else props.get('description'))
    if desc and allsrc:out['description']=desc
    def fact(label,value,sources=src):
        if value is not None and value!='' and sources:out['facts'].append({'label':label,'value':value,'sources':sources})
    if feat and src:
        ai=feat.get('ai_tagged',False)
        fact('Sectors'+(' (AI-tagged)' if ai is True or isinstance(ai,list) and 'sectors' in ai else ''),', '.join(feat['sectors']) if feat['sectors'] else None)
        fact('Stages'+(' (AI-tagged)' if ai is True or isinstance(ai,list) and 'stages' in ai else ''),', '.join(feat['stages']) if feat['stages'] else None)
        fact('Headquarters',feat.get('hq'));fact('Country',feat.get('country'))
        a=feat.get('amount') or {}; fact('Typical round size',f"{a['min']:g}–{a['max']:g}" if a.get('min') is not None and a.get('max') is not None else str(a.get('min') or a.get('max') or '') or None)
        act=feat.get('activity') or {};fact('Rounds in the last 24 months',act.get('rounds_24m'));fact('Rounds led in the last 24 months',act.get('led_24m'))
    rs=feat.get('rounds') if feat else []
    if not rs and entity_id in __import__('api.candidates',fromlist=['_enriched'])._enriched:rs=__import__('api.candidates',fromlist=['_enriched'])._enriched[entity_id]
    if typ=='investor':
        for r in rs or []:
            sources=r.get('sources') or []
            if not sources:continue
            x={'leads':[out['name']] if r.get('is_lead') else [],'investors':[out['name']],'sources':sources}
            for a,b in [('company','company'),('round_type','round_type'),('funding_amount','amount'),('year','date')]:
                if r.get(a) is not None:x[b]=str(r[a])
            out['rounds'].append(x)
    else:
        groups={}
        for e,n in edges:
            if e.get('rel')!='INVESTED_IN' or str(e.get('dst'))!=entity_id or not e.get('sources'):continue
            date=str(e.get('event_date') or ''); g=groups.setdefault(date,{'date':date,'investors':[],'leads':[],'sources':[]});g['investors'].append(n.get('name'))
            if e.get('is_lead'):g['leads'].append(n.get('name'))
            g['sources']=_union(g['sources'],e.get('sources'))
        out['rounds']=list(groups.values())
    for e,n in edges:
        if not e.get('sources'):continue
        if e.get('rel')=='INVESTED_IN' and str(e.get('src'))==entity_id:out['portfolio'].append({'id':str(n['id']),'name':n.get('name')})
        roles={'FOUNDED':'Founder','IS_CEO_OF':'CEO','IS_CTO_OF':'CTO','IS_BOARD_MEMBER_OF':'Board member','WORKS_AT':'Employee','IS_MEMBER_OF':'Member'}
        if e.get('rel') in roles and str(e.get('dst'))==entity_id:
            p={'id':str(n['id']),'name':n.get('name'),'role':roles[e['rel']]}
            if e.get('valid_since'):p['since']=e['valid_since']
            out['people'].append(p)
    if session_id:
        _session(session_id); prof=chat_store.get_profile(session_id) or {}; scored=score_candidate(normalize_profile(prof,mode,graph.view_seeds(session_id)),{'id':entity_id,'name':out['name'],'type':typ,'rounds':rs or [],'attrs':{'industries':feat.get('sectors',[]) if feat else props.get('industries',[]),'hq':feat.get('hq') if feat else props.get('hq'),'country':feat.get('country') if feat else props.get('country'),'sources':allsrc,'ai_tagged':feat.get('ai_tagged') if feat else False}})
        out['score']=scored['score'];out['confidence']=scored['confidence'];out['why_match']=[{'signal':s['signal'],'text':s['text'],'sources':s['sources']} for s in sorted((x for x in scored['signals'] if x['value'] is not None and x['sources']),key=lambda x:-x['weight']*x['value'])]
    return out
class ModeInput(BaseModel):mode:str
@router.post('/api/sessions/{session_id}/mode')
async def save_mode(session_id:str,body:ModeInput):
    _session(session_id); m=_mode(body.mode);chat_store.save_mode(session_id,m);return {'mode':m}
@router.get('/api/stats')
async def stats(catalog=Depends(get_catalog)):
    feats_i=catalog.list_features('investor');feats_s=catalog.list_features('startup'); out={'catalog':{'investors':len(feats_i),'startups':len(feats_s),'total':len({f['id'] for f in feats_i+feats_s}),'status':catalog.status()}}
    cala=get_cala()
    stat=getattr(cala,'stats',None) if cala else None
    if stat is not None:
        try:out['cala']=stat() if callable(stat) else stat
        except Exception:pass
    return out
