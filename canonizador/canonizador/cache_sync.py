"""Uploads the local cache to Valkey: `uv run python -m canonizador.cache_sync [carpeta ...]`.

Warms the demo cache and shares previously queried data with the team. Without folders, uses the
from the canonizer (`CANONIZADOR_CACHE` or `canonizador/cache`) and `backend/cache` if they exist.
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
    """Uploads each entry in `roots` to `remote`. Returns ({namespace: uploaded}, failed)."""
    uploaded, failed = {}, 0
    for root in roots:
        for namespace, digest, result in DiskCache(root).entries():
            if remote.put_key(namespace, digest, result):
                uploaded[namespace] = uploaded.get(namespace, 0) + 1
            else:
                failed += 1
                if not remote.available: return uploaded, failed  # remote unavailable: stop
    return uploaded, failed


def main(argv=None, remote=None):
    argv = sys.argv[1:] if argv is None else argv
    remote = remote or remote_from_env()
    if remote is None:
        print("VALKEY_URL is not set (environment or backend/.env); there is no shared cache to upload to.")
        return 1
    roots = [Path(a) for a in argv] or default_roots()
    if not roots:
        print("No local cache to upload.")
        return 0
    uploaded, failed = sync(roots, remote)
    for namespace in sorted(uploaded):
        print(f"{namespace}: {uploaded[namespace]}")
    print(f"Total: {sum(uploaded.values())} entries uploaded to Valkey.")
    if failed:
        print("Valkey did not respond: the upload is incomplete. Check VALKEY_URL and run again.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
