"""Prueba de red manual (no forma parte de pytest): intent fijo, sin LLM."""
import asyncio
import json
import tempfile

from canonizador.api import _env, answer_intent
from canonizador.client import CalaClient


async def main():
    _env()
    # Cache temporal para confirmar la respuesta actual de Cala en esta corrida.
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
