"""Acceso local al catálogo precalculado."""
import json, os, threading, time
from typing import Protocol


def _list(v):
    if v is None: return []
    if isinstance(v, str): return [v] if v.strip() else []
    if isinstance(v, (list, tuple, set)): return [str(x) for x in v if x is not None and str(x).strip()]
    return []

def normalize_features(raw):
    """Normaliza datos tolerando los formatos parciales del catálogo."""
    if isinstance(raw, (str, bytes)):
        try: raw=json.loads(raw)
        except Exception: return None
    if not isinstance(raw, dict): return None
    ident=raw.get('id'); name=raw.get('name')
    if not ident or not name: return None
    kinds=raw.get('kinds')
    if not isinstance(kinds, (list, tuple, set)): kinds=[]
    kinds=list(dict.fromkeys(x for x in [*(str(k).lower() for k in kinds if k), *(['investor'] if raw.get('is_investor') else []), *(['startup'] if raw.get('is_startup') else [])] if x in ('investor','startup')))
    sectors=_list(raw.get('sectors') if raw.get('sectors') is not None else raw.get('sector'))
    stages=_list(raw.get('stages') if raw.get('stages') is not None else raw.get('stage'))
    amount=raw.get('amount') if isinstance(raw.get('amount'),dict) else {}
    lo=amount.get('min',raw.get('amount_min')); hi=amount.get('max',raw.get('amount_max'))
    def num(v):
        try: return float(v) if v is not None else None
        except (TypeError,ValueError): return None
    activity=raw.get('activity') if isinstance(raw.get('activity'),dict) else {}
    rounds=raw.get('rounds') if isinstance(raw.get('rounds'),list) else []
    return {'id':str(ident),'name':str(name),'kinds':kinds,'description':raw.get('description') if isinstance(raw.get('description'),str) else '', 'sectors':sectors,'stages':stages,'ai_tagged':raw.get('ai_tagged',False),'country':raw.get('country'),'hq':raw.get('hq') or raw.get('region'),'amount':{'min':num(lo),'max':num(hi)},'activity':{'rounds_24m':num(activity.get('rounds_24m')),'led_24m':num(activity.get('led_24m'))},'rounds':rounds,'sources':_list_sources(raw.get('sources')),'loaded_at':raw.get('loaded_at')}

def _list_sources(v): return [x for x in v if isinstance(x,dict)] if isinstance(v,list) else []
class CatalogPort(Protocol):
    def list_features(self,kind:str)->list[dict]: ...
    def get_features(self,entity_id:str)->dict|None: ...
    def status(self)->dict: ...
class MemoryCatalog:
    def __init__(self,features=None,status=None):
        self._features={}
        if isinstance(features,dict): features=features.values()
        for raw in features or []:
            f=normalize_features(raw)
            if f:self._features[f['id']]=f
        self._status=status or {}
    def list_features(self,kind): return [f for f in self._features.values() if kind in f['kinds']]
    def get_features(self,entity_id): return self._features.get(str(entity_id))
    def status(self): return dict(self._status)
class ValkeyCatalog(MemoryCatalog):
    def __init__(self,remote=None,refresh_s=None):
        super().__init__(); self.remote=remote; self.refresh_s=float(refresh_s if refresh_s is not None else os.getenv('CATALOG_REFRESH_S','30')); self._stamp=0.; self._lock=threading.Lock(); self._refreshing=False
    def _load(self):
        if not self.remote:return
        def read(c):
            keys=list(c.scan_iter(match='cat:v1:feat:*',count=1000)); vals=[]
            for i in range(0,len(keys),500):
                pipe=c.pipeline(); pipe.mget(keys[i:i+500]); vals.extend(pipe.execute())
            return keys,vals,c.get('cat:v1:status')
        try: ok,data=self.remote._run(read)
        except Exception: ok,data=False,None
        if not ok or data is None:return
        keys,vals,status=data; fresh={}
        for key,val in zip(keys,vals):
            f=normalize_features(val)
            if f:fresh[f['id']]=f
        try: status=json.loads(status) if status else {}
        except Exception: status={}
        with self._lock:self._features=fresh; self._status=status if isinstance(status,dict) else {}; self._stamp=time.monotonic()
    def _maybe_refresh(self):
        if time.monotonic()-self._stamp < self.refresh_s:return
        with self._lock:
            if self._refreshing:return
            self._refreshing=True
        def run():
            try:self._load()
            finally:
                with self._lock:self._refreshing=False
        if self._stamp: threading.Thread(target=run,daemon=True).start()
        else:run()
    def list_features(self,kind):self._maybe_refresh();return super().list_features(kind)
    def get_features(self,entity_id):self._maybe_refresh();return super().get_features(entity_id)
    def status(self):self._maybe_refresh();return super().status()
_SINGLETON=None
def get_catalog():
    global _SINGLETON
    if _SINGLETON is None:
        try:
            from canonizador.cache import remote_from_env
            remote=remote_from_env()
        except Exception:remote=None
        _SINGLETON=ValkeyCatalog(remote) if remote else MemoryCatalog()
    return _SINGLETON
