"""Measures actual calls to the Cala entities endpoint."""
import argparse
import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from canonizador.client import CalaClient
from canonizador.cache import make_cache


NAMES = [
    "Amenitiz", "Mews", "Odoo", "Personio", "Pleo", "Wolt", "Bolt", "Wise", "Klarna", "Spotify",
    "Supercell", "Aiven", "ICEYE", "Silo AI", "Varjo", "Oura", "Swappie", "Revolut", "Monzo", "N26",
    "Checkout.com", "SumUp", "Mollie", "Adyen", "Northvolt", "Volocopter", "Celonis", "DeepL",
    "Trade Republic", "GetYourGuide", "Contentful", "Sennder", "Omio", "Babbel", "Personio", "Mambu",
    "Atomico", "Cherry Ventures", "Northzone", "Lifeline Ventures",
]


class NullCache:
    def get_key(self, namespace, key): return None
    def put_key(self, namespace, key, value): pass


class NoResponseCache(NullCache):
    """Disables response caching and keeps Valkey enabled for the shared rate limiter."""
    def __init__(self, remote=None): self.remote = remote


async def run(args):
    cache = NullCache() if args.sin_cache else None
    if args.sin_cache_local:
        configured_cache = make_cache("cache")
        cache = NoResponseCache(getattr(configured_cache, "remote", None))
    client = CalaClient(entities_interval=args.interval, entities_concurrency=args.concurrency,
                        cache=cache)
    first_429 = None
    start = time.monotonic()
    for index in range(args.n):
        name = NAMES[index % len(NAMES)] + (f" {index // len(NAMES) + 1}" if index >= len(NAMES) else "")
        try:
            await client.entities(name, "Company")
        except Exception as exc:
            if getattr(getattr(exc, "response", None), "status_code", None) == 429:
                first_429 = first_429 or index + 1
                break
            raise
    elapsed = time.monotonic() - start
    sent = client.calls
    print("| n | interval (s) | concurrency | total seconds | calls/s | 429 | first call with 429 | total wait (s) | shared limiter waits | shared limiter errors |")
    print("|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    print(f"| {sent} | {args.interval:g} | {args.concurrency} | {elapsed:.2f} | {sent / elapsed if elapsed else 0:.3f} | {client.stats['429']} | {first_429 or '—'} | {client.stats['429_wait_seconds']:.2f} | {client.stats['shared_limit_waits']} | {client.stats['shared_limit_errors']} |")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n", type=int, default=30)
    parser.add_argument("--interval", type=float, default=0.7)
    parser.add_argument("--concurrency", type=int, default=2)
    parser.add_argument("--sin-cache", action="store_true")
    parser.add_argument("--no-local-cache", action="store_true",
                        help="disables response caching and keeps Valkey enabled for the shared rate limiter")
    args = parser.parse_args()
    asyncio.run(run(args))


if __name__ == "__main__": main()
