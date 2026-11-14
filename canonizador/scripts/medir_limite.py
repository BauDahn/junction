"""Mide llamadas reales al endpoint de entidades de Cala."""
import argparse
import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from canonizador.client import CalaClient


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


async def run(args):
    client = CalaClient(entities_interval=args.interval, entities_concurrency=args.concurrency,
                        cache=NullCache() if args.sin_cache else None)
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
    print("| n | intervalo (s) | concurrencia | segundos totales | llamadas/s | 429 | primera llamada con 429 | espera total (s) |")
    print("|---:|---:|---:|---:|---:|---:|---:|---:|")
    print(f"| {sent} | {args.interval:g} | {args.concurrency} | {elapsed:.2f} | {sent / elapsed if elapsed else 0:.3f} | {client.stats['429']} | {first_429 or '—'} | {client.stats['429_wait_seconds']:.2f} |")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n", type=int, default=30)
    parser.add_argument("--interval", type=float, default=0.7)
    parser.add_argument("--concurrency", type=int, default=2)
    parser.add_argument("--sin-cache", action="store_true")
    args = parser.parse_args()
    asyncio.run(run(args))


if __name__ == "__main__": main()
