# Plan: Cala en el centro (14/11)

Cambio de enfoque decidido por el equipo: **el producto no es un chatbot; es una forma de usar Cala desde la voz.** Cada mensaje (texto o audio transcrito) se interpreta y, si hace falta, se convierte en consultas a Cala. Lo que se muestra son **los datos de Cala tal cual** (tablas con fuentes), no texto redactado por un modelo. Además, el usuario recibe un **journal diario** armado solo con datos de Cala.

## 1. Router: qué hacer con cada mensaje

Un mensaje puede traer varias cosas a la vez. El router lo divide en **partes** y clasifica cada una:

| Tipo | Ejemplo | Qué hace | Bloque que devuelve |
|---|---|---|---|
| `query` | "¿Quién lideró la Serie B de Amenitiz?" | Canonizador → consulta fija a Cala → resultado tal cual | `cala_table` (o `cala_answer`) |
| `claim` | "Mews levantó 50 millones" | Contrasta **lo que dijo el usuario** con Cala. Lo que devuelve Cala se da por correcto. | `claim_check` |
| `profile` | "Me interesan las fintech nórdicas en seed", "somos Stayflow…" | Actualiza el perfil y los gustos del usuario (alimentan el journal) | `profile_update` |
| `chitchat` | "gracias" | Respuesta mínima, sin consultar a Cala | `text` |

El modelo solo clasifica y extrae la intención. **Nunca escribe cifras ni nombres que no vengan de Cala.** Como mucho agrega una línea de resumen por bloque.

## 2. Ejecución de consultas: nunca "no hay información" sin haber probado todo

Para cada parte `query` o `claim`, se prueba en orden hasta obtener datos:

1. **Consulta canónica** (`POST /v1/knowledge/query`) con la plantilla fija del canonizador. Misma intención → misma cadena → misma respuesta (ver `docs/BENCHMARK-CANONIZADOR.md`).
2. **Entidades**: `entity_search` → `entity_introspection` → `entity_retrieval` de la empresa, persona o ronda, con propiedades, relaciones y fuentes.
3. **Búsqueda de Cala** (`POST /v1/knowledge/search`) con una pregunta canónica en inglés generada desde la intención (no el texto del usuario). Cala investiga en el momento y devuelve respuesta con fuentes.

Solo si los tres pasos vuelven vacíos se devuelve un bloque `not_found`, que dice **qué se buscó en cada herramienta** y lo más cercano que apareció. No se inventan datos para evitar ese bloque.

Todo pasa por la caché por consulta canónica, una llamada a Cala a la vez y reintentos ante 429.

## 3. Formato: tablas de Cala, no texto de chatbot

- **Filas de `knowledge_query`** → `cala_table` con las columnas tal como las devuelve Cala.
- **Entidad** → `cala_table` de campo · valor · fuente · fecha · tipo de fuente (`FILING`, `PRIMARY`, `PRESS`, `AGGREGATOR`).
- **`knowledge_search`** → `cala_answer`: el markdown de Cala tal cual, con sus fuentes.
- Cada bloque incluye **la consulta exacta** y la herramienta usada, para que se pueda reproducir.

## 4. Verificación de afirmaciones del usuario (`claim`)

1. Extraer la afirmación como intención (quién, qué atributo, qué valor dijo el usuario).
2. Consultar Cala con el mismo camino del punto 2.
3. Comparar el valor del usuario con el de Cala: `confirmed`, `contradicted`, `partially_confirmed` o `no_data`. Las reglas ya probadas en el verificador de decks se mantienen: la ausencia de evidencia no es contradicción, y un redondeo o una moneda equivalente cuentan como confirmación.
4. Devolver `claim_check` con el veredicto, la explicación de una línea y **la tabla de Cala como evidencia**.

## 5. Perfil y gustos

El perfil actual (startup del usuario) se amplía con:
- `role`: `founder` | `investor` | `other`.
- `interests`: `sectors`, `regions`, `stages`, y `follows` (empresas e inversores que quiere seguir).

Se llenan con las partes `profile` del router y alimentan el journal personalizado y las recomendaciones.

## 6. Journal diario (solo en la app)

Dos ediciones, armadas **solo con consultas a Cala** por plantillas fijas:

| Edición | Para quién | Secciones |
|---|---|---|
| `ecosistema` (genérica) | Todos | Rondas más grandes recientes por región · fondos más activos · adquisiciones · Slush 2026 |
| `founders` (personalizada) | Cada sesión, según su perfil | Rondas recientes en tus sectores y regiones · inversores que lideran rondas como la tuya (`is_lead`) · competidores que levantaron · adquisiciones en tu sector · asistentes a Slush 2026 de tu interés |

- **Generación**: bajo demanda la primera vez del día (y un botón "regenerar" para la demo); cada sección es una consulta canónica fija, cacheada. La edición genérica se comparte entre todos; las personalizadas reutilizan consultas por (sector, región).
- **Solo lo nuevo**: cada ítem guarda su fecha (`announcement_date` / `event_date`); el journal marca lo que es nuevo desde la edición anterior.
- **Preguntar desde el journal**: cada ítem tiene un botón para preguntar por audio o texto, que entra al mismo router con el ítem como contexto.
- Sin email (decisión del equipo): solo en la app.

## 7. Reparto y orden

| # | Qué | Quién | Depende de |
|---|---|---|---|
| A | Contrato en `docs/API.md` (bloques, perfil ampliado, journal) | bau | — |
| B | `backend/cala_core/`: router, ejecución con respaldo, formato de tablas, verificación de afirmaciones. Función pública `handle_message(text, profile, llm, cala)` → `{blocks, profile_patch}` | bau (Codex) | A |
| C | `backend/journal/`: generador y endpoints del journal | bau (Codex) | A, B |
| D | Conectar `cala_core.handle_message` al chat (`backend/chat/engine.py` y rutas): los mensajes devuelven `blocks` | fabricio | B |
| E | App: renderizar bloques (`cala_table`, `cala_answer`, `claim_check`, `profile_update`, `not_found`) en el chat | fabricio | A |
| F | App: pestaña Journal (dos ediciones, ítems con "preguntar") | fabricio | A, C |

Mientras B y C no estén, la app puede trabajar contra el modo simulado con ejemplos de los bloques del contrato.
