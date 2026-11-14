"""Sube la caché local a Valkey: `uv run python -m canonizador.cache_sync [carpeta ...]`.

Sirve para precalentar la demo y compartir con el equipo lo que ya se consultó. Sin carpetas usa la
del canonizador (`CANONIZADOR_CACHE` o `canonizador/cache`) y `backend/cache` si existen.
"""
import os
import sys
from pathlib import Path

from .cache import DiskCache, remote_from_env

REPO = Path(__file__).resolve().parents[2]


def default_roots():
    roots = [Path(os.getenv("CANONIZADOR_CACHE") or REPO / "canonizador" / "cache"), REPO / "backend" / "cache"]
    return [r for r in roots if r.is_dir()]


def sync(roots, remote):
    """Sube cada entrada de `roots` a `remote`. Devuelve ({namespace: subidas}, fallidas)."""
    uploaded, failed = {}, 0
    for root in roots:
        for namespace, digest, result in DiskCache(root).entries():
            if remote.put_key(namespace, digest, result):
                uploaded[namespace] = uploaded.get(namespace, 0) + 1
            else:
                failed += 1
                if not remote.available: return uploaded, failed  # remoto caído: no seguir
    return uploaded, failed


def main(argv=None, remote=None):
    argv = sys.argv[1:] if argv is None else argv
    remote = remote or remote_from_env()
    if remote is None:
        print("VALKEY_URL no está definida (entorno o backend/.env): no hay caché compartida a la que subir.")
        return 1
    roots = [Path(a) for a in argv] or default_roots()
    if not roots:
        print("No hay caché local que subir.")
        return 0
    uploaded, failed = sync(roots, remote)
    for namespace in sorted(uploaded):
        print(f"{namespace}: {uploaded[namespace]}")
    print(f"Total: {sum(uploaded.values())} entradas subidas a Valkey.")
    if failed:
        print("Valkey no respondió: la subida quedó incompleta. Revisá VALKEY_URL y volvé a correrlo.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
