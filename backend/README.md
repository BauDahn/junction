# Deck Verifier backend

Requiere Python 3.11+ y `uv`. Instala dependencias con `uv sync`. Configurá `CALA_API_KEY` y las claves del proveedor elegido en `.env`; no se muestran ni se guardan en reportes.

Generar el deck de ejemplo:

```sh
uv run python examples/make_sample_deck.py
```

Ejecutar la CLI:

```sh
LLM_PROVIDER=codex uv run python -m verifier examples/sample_deck.pdf
LLM_PROVIDER=nvidia uv run python -m verifier examples/sample_deck.pdf
LLM_PROVIDER=claude uv run python -m verifier examples/sample_deck.pdf
```

También se puede elegir proveedor con `--provider`. Los resultados de Cala y LLM se cachean en `cache/`. El score parte de 50 y suma 50 veces `(confirmadas + 0.5 × parciales − contradichas) / afirmaciones puntuadas`, acotado a 0–100; si no hay afirmaciones puntuadas queda en 50.

Tests: `uv run pytest`.
