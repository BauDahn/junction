"""Implementación local mínima de la interfaz del grafo."""
from typing import Protocol

def neighbors_batch(store, ids, rels=None):
    """Obtiene vecinos por lote y tolera almacenes que solo aceptan IDs escalares."""
    ids = list(ids or [])
    try:
        result = store.neighbors(ids, rels=rels) if rels is not None else store.neighbors(ids)
        if isinstance(result, dict):
            return {str(ident): result.get(str(ident), []) for ident in ids}
    except (TypeError, AttributeError):
        pass
    output = {}
    for ident in ids:
        try:
            result = store.neighbors(ident, rels=rels) if rels is not None else store.neighbors(ident)
        except (TypeError, AttributeError):
            result = []
        output[str(ident)] = result if isinstance(result, list) else []
    return output

class GraphPort(Protocol):
    def get_node(self,node_id): ...
    def get_nodes(self,ids): ...
    def get_edge(self,edge_id): ...
    def edges_of(self,node_id): ...
    def neighbors(self,node_id_or_ids,rels=None): ...
    def resolve(self,name): ...
    def view_seeds(self,user): ...
    def view_nodes(self,user): ...
    def set_view(self,user,seeds,nodes): ...
    def add_to_view(self,user,node_ids): ...
    def distance(self,sources,target,max_depth=3,within=None): ...
class MemoryGraph:
    def __init__(self):self.nodes={};self.edges={};self.adj={};self.alias={};self.views={}
    def add_node(self,node):
        self.nodes[str(node['id'])]=node
        for n in [node.get('name'),*(node.get('aliases') or [])]:
            if n:self.alias[n.casefold()]=str(node['id'])
    def add_edge(self,edge):
        e=dict(edge); self.edges[str(e['id'])]=e
        for n in (e.get('src'),e.get('dst')):self.adj.setdefault(str(n),[]).append(e)
    def get_node(self,node_id):return self.nodes.get(str(node_id))
    def get_nodes(self,ids):return {str(i):self.nodes[str(i)] for i in ids if str(i) in self.nodes}
    def get_edge(self,edge_id):return self.edges.get(str(edge_id))
    def edges_of(self,node_id):return list(self.adj.get(str(node_id),[]))
    def neighbors(self,node_id_or_ids,rels=None):
        def one(i):
            out=[]
            for e in self.edges_of(i):
                if rels and e.get('rel') not in rels:continue
                j=e.get('dst') if str(e.get('src'))==str(i) else e.get('src'); n=self.get_node(j)
                if n:out.append((e,n))
            return out
        return {str(i):one(i) for i in node_id_or_ids} if isinstance(node_id_or_ids,(list,tuple,set)) else one(node_id_or_ids)
    def resolve(self,name):return self.alias.get(str(name).casefold())
    def view_seeds(self,user):return list(self.views.get(str(user),(set(),set()))[0])
    def view_nodes(self,user):return set(self.views.get(str(user),(set(),set()))[1])
    def set_view(self,user,seeds,nodes):self.views[str(user)]=(set(seeds),set(nodes))
    def add_to_view(self,user,node_ids):
        s,n=self.views.get(str(user),(set(),set()));self.views[str(user)]=(s,n|set(node_ids))
    def distance(self,sources,target,max_depth=3,within=None):
        todo=list(dict.fromkeys(sources)); seen=set(todo); allowed=set(within) if within is not None else None
        for d in range(max_depth+1):
            if target in todo:return d
            nxt=[]
            for i in todo:
                for _,n in self.neighbors(i):
                    j=str(n['id'])
                    if j not in seen and (allowed is None or j in allowed):seen.add(j);nxt.append(j)
            todo=nxt
        return None
_GRAPH=None
def get_graph():
    global _GRAPH
    try:
        from graph import get_store
        return get_store()
    except Exception:
        if _GRAPH is None:_GRAPH=MemoryGraph()
        return _GRAPH
