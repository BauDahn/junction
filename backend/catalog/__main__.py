"""Slush catalog CLI: python -m catalog {run|export|import|status}."""
import argparse
import asyncio
import json
import sys

from .ingest import (
    CatalogLockError,
    STATUS_KEY,
    _json_load,
    _resolve_kv_and_store,
    export_catalog,
    import_catalog,
    run_catalog,
)


def build_parser():
    parser = argparse.ArgumentParser(prog="python -m catalog", description="Ingest and back up the Slush 2026 catalog")
    sub = parser.add_subparsers(dest="command", required=True)

    run_p = sub.add_parser("run", help="Runs resumable ingestion (stages 1 to 3)")
    run_p.add_argument("--limit", type=int, default=None, help="Maximum number of attendees to process")
    run_p.add_argument("--concurrency", type=int, default=2, help="Concurrency for Cala entity calls")
    run_p.add_argument("--max-calls", type=int, default=150, help="Maximum actual Cala calls in this run (0 = unlimited)")

    exp_p = sub.add_parser("export", help="Exports the catalog and graph to a JSON file (Plan B)")
    exp_p.add_argument("path", help="Output JSON file path")

    imp_p = sub.add_parser("import", help="Imports the catalog and graph from a JSON file")
    imp_p.add_argument("path", help="Backup JSON file path")

    sub.add_parser("status", help="Shows the current cat:v1:status state")
    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "run":
        if args.max_calls < 0:
            parser.error("--max-calls must be 0 or greater")
        if args.max_calls == 0:
            print("Warning: --max-calls 0 disables the per-run Cala call budget.", file=sys.stderr)
        try:
            result = asyncio.run(run_catalog(limit=args.limit, cala_concurrency=args.concurrency, max_calls=args.max_calls))
        except CatalogLockError as exc:
            print(str(exc), file=sys.stderr)
            return 1
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    if args.command == "export":
        result = export_catalog(args.path)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    if args.command == "import":
        result = import_catalog(args.path)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    if args.command == "status":
        kv, _ = _resolve_kv_and_store()
        status = _json_load(kv.get(STATUS_KEY)) or {}
        print(json.dumps(status, ensure_ascii=False, indent=2))
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
