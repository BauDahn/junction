# Canonizador de consultas Cala

Normaliza preguntas, convierte su intención a JSON con `codex exec` por defecto (o `LLM_PROVIDER=nvidia`), resuelve entidades y consulta endpoints de entidad con caché local en `cache/`.

Desde esta carpeta:

```sh
uv sync --extra dev
uv run python -m canonizador "¿Quién lideró la Serie B de Amenitiz?"
uv run python bench.py
uv run pytest
```

La CLI carga `CALA_API_KEY` desde `../backend/.env` si no está en el entorno. Las peticiones tienen caché cruda. `CalaClient` limita knowledge/query y knowledge/search con `knowledge_interval` (8 s) y entidades con `entities_interval` (0,7 s); se configuran también con `CALA_KNOWLEDGE_INTERVAL` y `CALA_ENTITIES_INTERVAL`. Las entidades permiten hasta 2 peticiones simultáneas (`entities_concurrency` / `CALA_ENTITIES_CONCURRENCY`). `CALA_429_WAIT` fija la espera exponencial base en segundos (5 por defecto); se respeta `Retry-After`, con un máximo de 60 s.

## Caché compartida (Aiven Valkey)

Las consultas a Cala tardan 16–60 s. Por defecto se cachean solo en disco (`cache/`, por máquina). Con `VALKEY_URL` definida, la caché pasa a tener dos capas: disco → Valkey. Lo que consulta una máquina le sale al instante a la otra.

Activarla:

1. En la [consola de Aiven](https://console.aiven.io): *Create service* → **Valkey** → elegir plan y región → esperar a que esté *Running*.
2. Copiar el **Service URI** (`rediss://default:<password>@<host>:<port>`, con TLS) a `backend/.env`:
   ```sh
   VALKEY_URL=rediss://default:<password>@<host>:<port>
   # CACHE_TTL_S=604800   # opcional: caducidad en segundos (por defecto 7 días; 0 = sin caducidad)
   # VALKEY_CONNECT_TIMEOUT=8  # conexión inicial (segundos)
   # VALKEY_TIMEOUT=3          # lectura/escritura (segundos)
   ```
   Es un secreto: va solo en `backend/.env`, igual que `CALA_API_KEY`.
3. Subir lo que ya está en disco (precalentar la demo): `uv run python -m canonizador.cache_sync` (imprime cuántas entradas subió por namespace; acepta carpetas de caché como argumentos; por defecto `canonizador/cache` y `backend/cache`).

Cómo funciona (`canonizador/cache.py`):

- `make_cache(root)` devuelve `LayeredCache(DiskCache, ValkeyCache)` si hay `VALKEY_URL`, y `DiskCache` si no. La usan `answer()` y `CalaClient` (respuestas crudas, namespace `cala`).
- Lectura: disco → Valkey (lo que viene de Valkey se copia al disco). Escritura: ambos.
- Claves `cala:v1:<namespace>:<sha256>`. Las respuestas de Cala caducan a los `CACHE_TTL_S` segundos; las intenciones del LLM (`intents`) no caducan.
- Valkey es opcional de verdad: timeout de conexión configurable (`VALKEY_CONNECT_TIMEOUT`, 8 s) y de lectura/escritura (`VALKEY_TIMEOUT`, 3 s). Si falla, se sigue solo con disco y no se reintenta durante 60 s. El backend intenta precalentar la conexión en segundo plano al arrancar.
- Ahorro para la demo: `cache.stats` (o `canonizador.cache.STATS`, acumulado del proceso) tiene `local_hits`, `remote_hits` y `misses`.
- En los tests la caché remota está desactivada (`VALKEY_URL=""` en `tests/conftest.py`).
