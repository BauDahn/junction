import asyncio
import json
import re
import statistics
import time
from pathlib import Path

from canonizador.api import answer, _env
from canonizador.client import CalaClient


def facts(value):
    return set(re.findall(r"[0-9a-f]{8}-[0-9a-f-]{27,}|\b\d+(?:[.,]\d+)?\s?(?:€|EUR|USD|\$|million|million euros)\b", json.dumps(value, ensure_ascii=False), re.I))


def jaccard(a, b): return len(a & b) / len(a | b) if a | b else 1.0


async def run():
    _env()
    groups = json.loads((Path(__file__).parent / "bench/questions.json").read_text())
    cala = CalaClient(cache_dir=Path(__file__).parent / "cache")
    lines = ["# Cala Query Canonicalizer Benchmark", "", "Metrics are computed over extracted UUIDs and numeric amount tokens; calls are cache-aware.", "", "| Group | Mode | Mean fact/entity Jaccard | Mean value Jaccard | Cala calls | Mean latency (s) |", "|---|---:|---:|---:|---:|---:|"]
    for group in groups:
        for mode in ("direct", "canonical"):
            outputs, times, before = [], [], cala.calls
            for q in group["questions"]:
                start = time.monotonic()
                outputs.append(await cala.search(q) if mode == "direct" else await answer(q))
                times.append(time.monotonic() - start)
            sets = [facts(o) for o in outputs]
            pairs = [jaccard(sets[i], sets[j]) for i in range(len(sets)) for j in range(i + 1, len(sets))]
            score = statistics.mean(pairs) if pairs else 1
            lines.append(f"| {group['group']} | {mode} | {score:.3f} | {score:.3f} | {cala.calls-before} | {statistics.mean(times):.1f} |".replace("cala.calls-before", str(cala.calls - before)))
    lines += ["", "Run with `uv run python bench.py` from `canonizador/`."]
    report = Path(__file__).parent / "REPORT.md"
    report.write_text("\n".join(lines) + "\n")
    print(report)


if __name__ == "__main__": asyncio.run(run())
