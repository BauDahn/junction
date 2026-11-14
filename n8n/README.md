# Workflows n8n de Junction

Estos tres workflows exportados cubren la integración solicitada en Issue #47. Usan el contrato de `docs/API.md`: sesiones/mensajes y jobs del verificador están en `main`; los endpoints del Journal pertenecen al trabajo #31 y hoy pueden responder 404 hasta que se integre.

## Workflows

- `journal_diario_workflow.json`: edición ecosistema o founders, regeneración y polling cada 2 s; permite preguntar desde un ítem del journal.
- `verificador_deck_workflow.json`: acepta el deck de muestra o PDF multipart, consulta el job y prepara reporte Markdown con alerta.
- `cala_consulta_voz_workflow.json`: crea una sesión si hace falta, consulta `/api/sessions/{id}/messages` y conserva bloques, fuentes y CalaCall.

Los flujos consultan Cala a través del backend. Así se conserva el canonizador y la caché de disco/Aiven Valkey; no se envía texto libre directamente mediante `github.com/cala-ai/cala-n8n-node`, porque eso omitiría esa capa y permitiría consultas inconsistentes. Las llamadas a Cala pueden tardar 16–60 s y Cala limita con HTTP 429 tras aproximadamente 7 llamadas seguidas. Los requests largos llevan timeout de 120 s y reintentos espaciados para 429/502 cuando corresponde.

## Importación

En la UI de n8n: **Workflows → Import from File** y selecciona cada JSON. Revisa credenciales/permisos y activa el workflow después de importar si quieres habilitar los webhooks.

Con CLI n8n v1+: `n8n import:workflow --input=n8n/journal_diario_workflow.json` (repite cambiando el archivo para los otros workflows). Según la instalación, el CLI requiere que n8n esté parado y usa la base de datos configurada para esa instancia.

Configura `JUNCTION_API_URL` en el entorno del proceso de n8n (por ejemplo `http://localhost:8000` si backend y n8n comparten host; dentro de Docker usa el hostname de servicio, no localhost). Si no se define, el valor de respaldo del workflow es `http://localhost:8000`. El acceso a `$env` puede estar restringido por configuración/hosting de n8n; en ese caso habilita el acceso a variables de entorno para Code nodes o reemplaza la expresión por una variable de entorno permitida en tu despliegue.

## Estado de endpoints

`GET/POST /api/journal/*` y `/api/sessions/{id}/journal*` están en desarrollo en Issue #31 y devuelven 404 hasta su merge. Los endpoints `/api/verify`, `/api/verify-sample`, `/api/jobs/{job_id}` y `/api/sessions/*/messages` ya están en `main` según `docs/API.md`.

## Pruebas rápidas

Journal genérico:

```sh
curl -X POST http://localhost:5678/webhook/junction-journal \
  -H 'Content-Type: application/json' \
  -d '{"edition":"ecosistema","date":"2026-11-14"}'
```

Journal founders con pregunta vinculada:

```sh
curl -X POST http://localhost:5678/webhook/junction-journal \
  -H 'Content-Type: application/json' \
  -d '{"edition":"founders","session_id":"SESSION_ID","question":"¿Quién lideró esta ronda?","journal_item_id":"ITEM_ID"}'
```

Verificador con muestra:

```sh
curl -X POST http://localhost:5678/webhook/junction-verify-deck \
  -H 'Content-Type: application/json' -d '{"mode":"sample"}'
```

Verificador con PDF (el binary field esperado por el workflow se llama `file`):

```sh
curl -X POST http://localhost:5678/webhook/junction-verify-deck -F 'file=@pitch.pdf'
```

Consulta Cala:

```sh
curl -X POST http://localhost:5678/webhook/junction-cala-query \
  -H 'Content-Type: application/json' \
  -d '{"text":"¿Qué startups finlandesas levantaron una ronda seed?","context":{}}'
```
