"""Enriquecimiento opcional de rondas en segundo plano."""
import asyncio
import os
from .profiles import investor_rounds

_rounds = {}
_failed = set()
_active = set()
_tasks = set()


def rounds_for(ident):
    return _rounds.get(str(ident), [])


async def _load(ident, name, cala):
    try:
        result = await investor_rounds(cala, name)
        _rounds[ident] = result.get("rounds", [])
    except Exception:
        _failed.add(ident)
    finally:
        _active.discard(ident)


def schedule(results, cala):
    try:
        remaining = max(0, int(os.getenv("FEED_ENRICH_TOP", "0")))
    except ValueError:
        remaining = 0
    if not cala or not remaining:
        return
    for result in results:
        if not remaining:
            break
        ident = str(result.get("id") or "")
        candidate = result.get("_candidate") or {}
        if candidate.get("rounds"):
            continue
        if not ident or ident in _active or ident in _failed or ident in _rounds:
            continue
        _active.add(ident)
        remaining -= 1
        task = asyncio.create_task(_load(ident, result.get("name", ""), cala))
        _tasks.add(task)
        task.add_done_callback(_tasks.discard)


def reset():
    _rounds.clear()
    _failed.clear()
    _active.clear()
    for task in list(_tasks):
        task.cancel()
    _tasks.clear()
