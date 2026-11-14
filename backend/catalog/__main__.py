"""CLI del catálogo de Slush: python -m catalog {run|export|import|status}."""
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
    parser = argparse.ArgumentParser(prog="python -m catalog", description="Ingesta y respaldo del catálogo de Slush 2026")
    sub = parser.add_subparsers(dest="command", required=True)

    run_p = sub.add_parser("run", help="Ejecuta la ingesta reanudable (etapas 1 a 3)")
    run_p.add_argument("--limit", type=int, default=None, help="Tope máximo de asistentes a procesar")
    run_p.add_argument("--concurrency", type=int, default=2, help="Concurrencia de llamadas a entidades en Cala")

    exp_p = sub.add_parser("export", help="Exporta catálogo y grafo a un archivo JSON (Plan B)")
    exp_p.add_argument("path", help="Ruta del archivo JSON de salida")

    imp_p = sub.add_parser("import", help="Importa catálogo y grafo desde un archivo JSON")
    imp_p.add_argument("path", help="Ruta del archivo JSON de respaldo")

    sub.add_parser("status", help="Muestra el estado actual de cat:v1:status")
    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "run":
        try:
            result = asyncio.run(run_catalog(limit=args.limit, cala_concurrency=args.concurrency))
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
