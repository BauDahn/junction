"""Construcción rápida del feed sobre datos locales."""
import time
from .affinity import rank, score_candidate, ticket_bounds
from .enrich import rounds_for
from .graph_port import neighbors_batch

_BFS = {}


def _uniq(values):
    result = []
    seen = set()
    for value in values:
        if value is None or not str(value).strip():
            continue
        text = str(value).strip()
        key = text.casefold()
        if key not in seen:
            seen.add(key)
            result.append(text)
    return result


def normalize_profile(profile, mode, seeds):
    profile = profile or {}
    interests = profile.get("interests") or {}
    raising = profile.get("raising") or {}
    understood = profile.get("what_we_understood") or {}
    sectors = [value for value in (interests.get("sectors") or [])
               if str(value).strip().casefold() != "other"]
    focus = understood.get("sector_focus")
    focus = focus if isinstance(focus, (list, tuple)) else [focus]
    focus = [value for value in focus if value is not None and str(value).strip().casefold() != "other"]
    if not sectors and focus:
        sectors = focus
    profile_sector = profile.get("sector")
    if profile_sector and str(profile_sector).strip().casefold() == "other":
        profile_sector = None
    sectors = _uniq(([profile_sector] if profile_sector else []) + sectors)
    regions = _uniq(([profile.get("location")] if profile.get("location") else [])
                    + (interests.get("regions") or []))
    if mode == "raising":
        stages = _uniq([raising.get("round") or profile.get("stage")])
    else:
        stages = _uniq((interests.get("stages") or [])
                       + ([profile.get("stage")] if profile.get("stage") else []))
    bounds = ticket_bounds(profile.get("ticket_range")) or ticket_bounds(profile.get("ticket"))
    if bounds is None and mode == "raising":
        bounds = ticket_bounds(raising.get("amount"))
    ticket = {"min": bounds[0], "max": bounds[1]} if bounds is not None else None
    return {"sectors": sectors, "stage": stages[0] if stages else None, "stages": stages,
            "regions": regions, "ticket": ticket, "seeds": list(seeds or [])}


def seed_names(profile):
    profile = profile or {}
    interests = profile.get("interests") or {}
    follows = interests.get("follows") or {}
    names = ([profile.get("startup_name")] if profile.get("startup_name") else [])
    return _uniq(names + (profile.get("competitors") or [])
                 + (follows.get("companies") or []) + (follows.get("investors") or []))


def _seeds(session_id, profile, store):
    seeds = store.view_seeds(session_id)
    if not seeds:
        seeds = [store.resolve(name) for name in seed_names(profile)]
    return list(dict.fromkeys(str(seed) for seed in seeds if seed))


def bfs_for_user(session_id, profile, store):
    seeds = _seeds(session_id, profile, store)
    key = (str(session_id), tuple(sorted(seeds)))
    now = time.monotonic()
    cached = _BFS.get(key)
    if cached and now - cached[0] < 30:
        return seeds, cached[1]
    distance = {seed: (0, []) for seed in seeds}
    nodes = {}
    edges = {}
    frontier = list(seeds)
    for depth in range(1, 4):
        batch = neighbors_batch(store, frontier)
        next_frontier = []
        for ident in frontier:
            for edge, node in batch.get(str(ident), []):
                node_id = str(node.get("id"))
                nodes[node_id] = node
                edges[str(edge.get("id") or repr(sorted(edge.items()))) ] = edge
                sources = edge.get("sources") or []
                if not sources or node_id in distance:
                    continue
                distance[node_id] = (depth, sources)
                next_frontier.append(node_id)
        frontier = list(dict.fromkeys(next_frontier))
        if not frontier:
            break
    data = {"distance": distance, "nodes": nodes, "edges": list(edges.values())}
    _BFS[key] = (now, data)
    return seeds, data


def _graph_candidate(ident, kind, graph_data):
    node = graph_data["nodes"].get(str(ident))
    if not node:
        return None
    related = [edge for edge in graph_data["edges"]
               if (str(edge.get("src")) == str(ident) or str(edge.get("dst")) == str(ident))
               and edge.get("rel") == "INVESTED_IN" and edge.get("sources")]
    qualifies = any(str(edge.get("src")) == str(ident) for edge in related) if kind == "investor" else any(
        str(edge.get("dst")) == str(ident) for edge in related)
    if not qualifies:
        return None
    props = node.get("props") or {}
    sources = props.get("sources") or node.get("sources") or []
    return {"id": str(ident), "name": node.get("name"), "type": kind, "rounds": rounds_for(ident),
            "attrs": {"industries": props.get("industries", []) if sources else [],
                      "hq": props.get("hq") if sources else None,
                      "country": props.get("country") if sources else None, "sources": sources}}


def candidate_for_entity(ident, session_id, profile, mode, catalog, store):
    features = catalog.get_features(ident)
    node = store.get_node(ident)
    if not features and not node:
        return None
    seeds, graph_data = bfs_for_user(session_id, profile, store)
    distance = graph_data["distance"].get(str(ident))
    kinds = features.get("kinds", []) if features else []
    if len(kinds) == 1:
        kind = kinds[0]
    elif len(kinds) > 1:
        kind = "investor" if mode == "raising" else "startup"
    else:
        kind = "investor" if mode == "raising" else "startup"
    candidate = _feature_candidate(features, kind, graph_data, ident) if features else None
    if candidate is None and node:
        edges = neighbors_batch(store, [ident]).get(str(ident), [])
        local_data = {"nodes": {str(ident): node}, "edges": [edge for edge, _ in edges]}
        candidate = _graph_candidate(ident, kind, local_data)
        if candidate is None:
            props = node.get("props") or {}
            sources = props.get("sources") or node.get("sources") or []
            candidate = {"id": str(ident), "name": node.get("name"), "type": kind,
                         "rounds": rounds_for(ident),
                         "attrs": {"industries": props.get("industries", []) if sources else [],
                                   "hq": props.get("hq") if sources else None,
                                   "country": props.get("country") if sources else None, "sources": sources}}
    if candidate is None:
        return None
    candidate["distance"] = distance[0] if distance else None
    candidate["distance_sources"] = distance[1] if distance else []
    candidate["features"] = features or {}
    return score_candidate(normalize_profile(profile, mode, seeds), candidate) | {
        "_candidate": candidate, "_features": features or {}}


def _feature_candidate(features, kind, graph_data, ident):
    if kind not in features.get("kinds", []):
        return None
    distance = graph_data["distance"].get(str(ident))
    return {"id": features["id"], "name": features["name"], "type": kind,
            "rounds": features.get("rounds") or rounds_for(ident),
            "attrs": {"industries": features.get("sectors", []), "hq": features.get("hq"),
                      "country": features.get("country"), "ai_tagged": features.get("ai_tagged"),
                      "sources": features.get("sources", [])},
            "features": {"stages": features.get("stages", []), "amount": features.get("amount", {}),
                         "activity": features.get("activity", {}), "sources": features.get("sources", [])},
            "distance": distance[0] if distance else None,
            "distance_sources": distance[1] if distance else [], "features_record": features}


def build_feed(session_id, profile, mode, catalog, store, today=None):
    seeds, graph_data = bfs_for_user(session_id, profile, store)
    kind = "investor" if mode == "raising" else "startup"
    features = catalog.list_features(kind)
    seen = set()
    candidates = []
    for feature in features:
        ident = feature["id"]
        if ident in seeds:
            continue
        seen.add(ident)
        candidate = _feature_candidate(feature, kind, graph_data, ident)
        if candidate is None:
            continue
        candidates.append(candidate)
    for ident in graph_data["distance"]:
        if ident in seen or ident in seeds:
            continue
        candidate = _graph_candidate(ident, kind, graph_data)
        if candidate:
            distance, sources = graph_data["distance"][ident]
            candidate["distance"] = distance
            candidate["distance_sources"] = sources
            candidates.append(candidate)
    normalized = normalize_profile(profile, mode, seeds)
    results = []
    for candidate in candidates:
        result = score_candidate(normalized, candidate, today=today)
        result["_candidate"] = candidate
        result["_features"] = candidate.get("features_record", {})
        results.append(result)
    ordered = rank(results)
    status = catalog.status()
    notes = []
    if not features or status and status.get("done", 0) < status.get("total", 0):
        note = (f"Catalog is still loading: {status.get('done', 0)} of {status.get('total', 0)} profiled."
                if status else "Catalog is still loading.")
        notes.append(note)
    if not any((normalized["sectors"], normalized["stage"], normalized["regions"], normalized["ticket"])):
        notes.append("Add your sector, stage and region to get better matches.")
    if not seeds:
        notes.append("Your company is not in the graph yet: matches use your profile only.")
    return {"results": ordered, "note": " ".join(notes) or None}
