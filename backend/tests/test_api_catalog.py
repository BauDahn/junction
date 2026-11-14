import json
from api.catalog_port import MemoryCatalog, ValkeyCatalog, normalize_features

def test_normalize_features_aliases_and_missing_fields():
    f=normalize_features({'id':4,'name':'A','is_investor':True,'sector':'AI','stage':'Seed','amount_min':'10','region':'Nordics'})
    assert f['kinds']==['investor'] and f['sectors']==['AI'] and f['stages']==['Seed']
    assert f['amount']=={'min':10.0,'max':None} and f['hq']=='Nordics' and f['sources']==[]
    assert normalize_features({'id':'x'}) is None

def test_valkey_reads_features_in_batches_not_gets():
    raw={'name':'X','kinds':['investor']}
    class Pipe:
        def __init__(self,c):self.c=c;self.keys=[]
        def mget(self,keys):self.keys=keys
        def execute(self):return [json.dumps(raw | {'id':key.rsplit(':',1)[-1]}) for key in self.keys]
    class Client:
        def __init__(self):self.gets=[];self.pipes=0
        def scan_iter(self,**kw):return [f"cat:v1:feat:{i}" for i in range(501)]
        def pipeline(self):self.pipes+=1;return Pipe(self)
        def get(self,key):self.gets.append(key);return '{}'
    class Remote:
        def __init__(self):self.client=Client()
        def _run(self,fn):return True,fn(self.client)
    remote=Remote();cat=ValkeyCatalog(remote,refresh_s=30)
    assert len(cat.list_features('investor'))==501
    assert remote.client.pipes==2 and remote.client.gets==['cat:v1:status']
