# Canonizador de consultas Cala

Normaliza preguntas, convierte su intención a JSON con `codex exec` por defecto (o `LLM_PROVIDER=nvidia`), resuelve entidades y consulta endpoints de entidad con caché local en `cache/`.

Desde esta carpeta:

```sh
uv sync --extra dev
uv run python -m canonizador "¿Quién lideró la Serie B de Amenitiz?"
uv run python bench.py
uv run pytest
```

La CLI carga `CALA_API_KEY` desde `../backend/.env` si no está en el entorno. Las peticiones Cala son secuenciales y tienen caché cruda. El benchmark directo y canonizado se ejecuta con `bench.py`.
