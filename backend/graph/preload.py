"""Precarga manual del vecindario para una demo."""
import argparse
import asyncio
import json
import sys

from canonizador.client import CalaClient
from .loader import load_neighborhood, resolve_seeds
from .store import get_store

NORDIC_FUNDS = ["Creandum", "EQT Ventures", "Northzone", "Lifeline Ventures", "Maki.vc", "Inventure", "byFounders", "Icebreaker.vc", "Seed Capital"]


def _names(values, file_path=None):
    result = []
    for value in values or []:
        result.extend(part.strip() for part in value.split(",") if part.strip())
    if file_path:
        with open(file_path, encoding="utf-8") as stream:
            result.extend(line.strip() for line in stream if line.strip() and not line.lstrip().startswith("#"))
    return list(dict.fromkeys(result))


async def run(args, store=None, cala=None):
    store = store or get_store()
    cala = cala or CalaClient()
    names = _names(getattr(args, "seeds", []), getattr(args, "seeds_file", None))
    if getattr(args, "nordic", False):
        names = list(dict.fromkeys(names + NORDIC_FUNDS))
    resolved = {"cala_calls": 0}
    seed_ids = await resolve_seeds(store, cala, names, stats=resolved)
    seed_map = {}
    for name in names:
        seed_id = store.resolve(name)
        if seed_id:
            seed_map[name] = seed_id
    if not seed_map:
        result = {"backend": getattr(store, "backend", "memory"), "user": args.user,
                  "seeds": {}, "error": "no seeds resolved",
                  "cala_calls": resolved["cala_calls"]}
        print(json.dumps(result, ensure_ascii=False))
        return result
    stats = await load_neighborhood(store, cala, seed_ids, user=args.user, depth=args.depth,
                                    quota=args.quota, introspect=getattr(args, "introspect", False))
    # Resolver calls pueden venir en caché; http_calls cuenta solo peticiones salidas.
    stats["cala_calls"] += resolved["cala_calls"]
    result = {"backend": getattr(store, "backend", "memory"), "user": args.user,
              "seeds": seed_map, **stats,
              "http_calls": getattr(cala, "calls", 0), "store": store.stats()}
    if hasattr(cala, "stats"):
        result["cala_stats"] = dict(cala.stats)
    if result["backend"] == "memory":
        print("Aviso: el backend memory no persiste la precarga.", file=sys.stderr)
    print(json.dumps(result, ensure_ascii=False))
    return result


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--user", required=True)
    parser.add_argument("--seeds", action="append", default=[])
    parser.add_argument("--seeds-file")
    parser.add_argument("--depth", type=int, default=2)
    parser.add_argument("--quota", type=int, default=15)
    parser.add_argument("--nordic", action="store_true")
    parser.add_argument("--introspect", action="store_true")
    args = parser.parse_args(argv)
    return asyncio.run(run(args))


if __name__ == "__main__":
    result = main()
    if result.get("error") == "no seeds resolved":
        raise SystemExit(1)
