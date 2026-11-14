# Qué construyó Codex

Reto de OpenAI Codex. En este proyecto **Claude planifica, revisa y prueba, y Codex escribe el código**: Claude le pasa una tarea concreta (archivos, criterio de hecho y cómo verificar) con `cx`, Codex la implementa en un sandbox y devuelve un resumen corto (`LISTO`/`BLOQUEADO`/`NECESITA`, archivos y verificación). Claude revisa el diff, corre las pruebas contra Cala real y pide correcciones en el mismo hilo (`cx seguir`).

Cada rol usa el modelo que le corresponde (`cx roles`): backend y frontend con `gpt-6-luna` y esfuerzo medio, tareas triviales con `gpt-5.6-luna` y esfuerzo bajo.

## Máquina `bau`

**12 tareas · 24 min de Codex · 8.0 M tokens de entrada (94% en caché) · 134 k tokens de salida.**

| Fecha | Rol | Modelo | Tarea (resumen) | Resultado | Min |
|---|---|---|---|---|---|
| 14/11 02:20 | backend | gpt-6-luna | Implementá la parte backend del verificador de decks según docs/SPEC-verificador.md: secciones Stack, Módulos 1-5 (config, cala, llm con los… | LISTO: Backend del verificador, deck de ejemplo, CLI y tests implementados; no incluye `app.py` ni la UI. | 3.2 |
| 14/11 02:25 | backend | gpt-6-luna | (seguir) Probé la CLI real con Cala + Codex: funciona (59 s), pero corregí esto en pipeline.py y el deck de ejemplo: 1) Extracción: hoy saca… | LISTO: Ajusté la extracción para excluir marketing, forcé la consulta de afirmaciones públicas de terceros y a | 1.5 |
| 14/11 02:25 | frontend | gpt-6-luna | Implementá app.py (en demo/) y la UI demo/static/index.html del verificador de decks según docs/SPEC-verificador.md, secciones 6 (app.py) y … | LISTO: Implementé la API de jobs y la UI responsive del verificador. | 1.9 |
| 14/11 02:29 | backend | gpt-6-luna | (seguir) La corrida real falló: 'Codex excedió el timeout de 180 segundos' (ahora hay más claims). Cambios: 1) Timeout del CodexProvider con… | LISTO: `CODEX_TIMEOUT` configura el timeout de Codex (default 420 s); los errores indican si falló `extract` o | 1.6 |
| 14/11 02:31 | frontend | gpt-6-luna | (seguir) El pipeline ya expone progreso: verify_pdf acepta on_progress(stage, done, total) (leé demo/verifier/pipeline.py). Conectalo en app… | LISTO: Conecté el progreso por etapas y el tiempo transcurrido. | 1.0 |
| 14/11 02:32 | backend | gpt-6-luna | En demo/verifier/pipeline.py, el prompt del juez marca 'contradicted' cuando Cala dice 'I was unable to find any evidence that X'. Eso está … | LISTO: el juez distingue ausencia de evidencia de una contradicción y extrae métricas internas como no verific | 0.8 |
| 14/11 03:13 | backend | gpt-6-luna | Implementá el canonizador de consultas a Cala según docs/SPEC-canonizador.md (leé también docs/CALA-CAMPOS.md). Todo dentro de canonizador/ … | LISTO: Implementé el paquete independiente en `canonizador/`, con normalización, proveedor LLM configurable, r | 3.2 |
| 14/11 03:27 | backend | gpt-6-luna | (seguir) La corrida real falló en canonizador/canonizador/intent.py (CodexProvider). Dos arreglos: (1) el schema no cumple el modo estricto:… | LISTO: CodexProvider ahora genera schemas estrictos, cierra stdin, usa timeout de 120 s con stderr al agotarse | 0.6 |
| 14/11 03:28 | backend | gpt-6-luna | (seguir) El intent ya funciona (las 3 variantes resuelven a Amenitiz db95edaa-058f-494d-a4f4-5f56bf81afd9), pero el retrieval da 422. Probé … | LISTO: El retrieval de rondas filtra localmente, envía a Cala solo claves admitidas y pide propiedades según l | 2.6 |
| 14/11 03:49 | backend | gpt-6-luna | Implementá la 'Fase 2' de docs/SPEC-canonizador.md en canonizador/ (leé esa sección, docs/CALA-SKILL.md y el código actual de canonizador/ca… | LISTO: Fase 2 implementada en `canonizador/`; la consulta de Amenitiz marcó la discrepancia entre Cala y entid | 3.6 |
| 14/11 03:54 | backend | gpt-6-luna | (seguir) Probé con el LLM real. Amenitiz: las 4 variantes dan la misma cadena y la misma respuesta (bien). Filtros: fallan en la normalizaci… | LISTO: filtros normalizados de forma determinista; ambos casos generan la misma consulta y el plan corrige la  | 1.7 |
| 14/11 04:04 | backend | gpt-6-luna | Bug en canonizador/ (leé canonizador/canonizador/api.py, plan.py, client.py). Con el LLM real, las listas (company_list) funcionan, pero TOD… | LISTO: separé la respuesta principal del enriquecimiento y ajusté el cuerpo de retrieval al contrato de Cala. | 2.2 |

Lo que salió de estas tareas: el verificador de decks completo (backend, CLI, API y UI), el canonizador de consultas a Cala (intención, resolución de entidades, plantillas fijas, caché, cruce con entidades) y sus correcciones tras probar contra la API real.

## Máquina `fabricio`

*(Pendiente: Fabricio agrega su registro de `cx log`. Su trabajo incluye la app Expo, el chat del backend, el audio con Whisper y las recomendaciones.)*

## Máquina `gabriel`

**8 tareas · 20 min de Codex · 9,597,599 tokens de entrada (95% en caché) · 191,590 tokens de salida.**

| Fecha | Rol | Modelo | Tarea (resumen) | Resultado | Min |
|---|---|---|---|---|---|
| 14/11 16:34 | backend | gpt-6-luna | Lee docs/API.md, docs/PLAN-CALA-CENTRO.md y CLAUDE.md (solo las secciones necesarias). Implementa el | LISTO: creados los 3 workflows y la documentación de Issue #47. | 2.5 |
| 14/11 16:39 | backend | gpt-6-luna | (seguir) Please fix all 4 defects in the three workflow JSON files under n8n/ (n8n/journal_diario_wo | LISTO: corregidos los cuatro defectos en los workflows; todos los nodos Code pasan parseo de JavaScr | 7.5 |
| 14/11 16:49 | backend | gpt-6-luna | (seguir) Aplica exactamente estos 3 reemplazos UTF-8 precisos en los archivos de `n8n/` usando Pytho | LISTO: aplicados los tres reemplazos UTF-8 solicitados. | 0.4 |
| 14/11 16:51 | backend | gpt-6-luna | (seguir) Durante la validación final de `n8n/*.json` detectamos 4 detalles funcionales puntuales por | LISTO: aplicados los cuatro ajustes solicitados. | 1.6 |
| 14/11 21:05 | backend | gpt-6-luna | (seguir) Aplica todas las correcciones de revisión señaladas por `fabricio` en el PR #61 (`Review 59 | LISTO: actualizados los tres workflows y `n8n/README.md`; JSON, conexiones, reintentos, JavaScript y | 4.2 |
| 14/11 21:20 | backend | gpt-6-luna | Implementa el Issue #66 ("Contexto: subir PDF (pitch) y notas de voz que alimentan el perfil") para | Listo. Espero la tarea concreta. | 0.1 |
| 14/11 21:20 | backend | gpt-6-luna | (seguir) La tarea concreta ya está en mi mensaje anterior (Issue #66: implementar backend/context/__ | LISTO: Issue #66 implementado; contexto extrae PDF, voz y notas, y actualiza el perfil. | 3.4 |
| 14/11 21:24 | backend | gpt-6-luna | (seguir) Revisión del diff de Issue #66: corrige 3 detalles concretos sin tocar nada fuera de backen | LISTO: Corregidos los tres detalles y agregada la prueba de persistencia al vaciar `geography`. | 0.8 |

Lo que salió de estas tareas: integración inicial de flujos `n8n/` (#47) y la ingesta de contexto del backend en `backend/context/` para Cala Match (#66: extracción de PDF, notas de voz y notas de texto hacia el perfil y etiquetas editables).

## Cómo regenerar

Cada máquina tiene su registro en `~/agentes/estado/codex.jsonl` (`cx log` lo resume).
