"""Manual network check (not part of pytest): fixed intent, no LLM."""
import asyncio
import json
import tempfile

from canonizador.api import _env, answer_intent
from canonizador.client import CalaClient


async def main():
    _env()
    # Temporary cache to verify Cala's current response in this run.
    with tempfile.TemporaryDirectory(prefix="cala-amenitiz-network-") as cache:
        cala = CalaClient(cache_dir=cache)
        intent = {
            "entities": [{"name": "Amenitiz", "type": "Company"}],
            "attribute": "lead_investors",
            "filters": {"round_label": "SERIES_B"},
        }
        result = await answer_intent(intent, cala)
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
