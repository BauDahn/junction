"""Fakes compartidos para pruebas del grafo."""
import fnmatch

class FakeRedis:
    def __init__(self): self.data, self.ttl, self.trips = {}, {}, 0
    def get(self,k): self.trips+=1; return self.data.get(k)
    def mget(self,ks):
        if ks: self.trips+=1
        return [self.data.get(k) for k in ks]
    def set(self,k,v,ex=None): self.trips+=1; self.data[k]=v; self.ttl[k]=ex; return True
    def delete(self,*ks):
        self.trips+=1
        for k in ks: self.data.pop(k,None); self.ttl.pop(k,None)
    def sadd(self,k,*xs): self.trips+=1; self.data.setdefault(k,set()).update(xs)
    def srem(self,k,*xs): self.trips+=1; self.data.get(k,set()).difference_update(xs)
    def smembers(self,k): self.trips+=1; return set(self.data.get(k,set()))
    def expire(self,k,t): self.ttl[k]=t
    def ping(self): self.trips+=1; return True
    def pipeline(self): return Pipe(self)
    def scan_iter(self,match):
        self.trips+=1
        return (k for k in self.data if fnmatch.fnmatch(k,match))

class Pipe:
    def __init__(self,c): self.c,self.ops=c,[]
    def __getattr__(self,method):
        def queue(*args,**kwargs): self.ops.append((method,args,kwargs)); return self
        return queue
    def execute(self):
        before=self.c.trips; result=[]
        for method,args,kwargs in self.ops:
            if method=="get": result.append(self.c.data.get(args[0]))
            elif method=="set": result.append(self.c.set(*args,**kwargs))
            elif method=="sadd": result.append(self.c.sadd(*args,**kwargs))
            elif method=="expire": result.append(self.c.expire(*args,**kwargs))
            elif method=="delete": result.append(self.c.delete(*args,**kwargs))
            elif method=="smembers": result.append(set(self.c.data.get(args[0],set())))
        self.c.trips=before+1
        return result
