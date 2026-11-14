# Proceso y decisiones

Una línea por hito: fecha y hora, qué se decidió o construyó, con qué herramienta (Codex, Nemotron, Cala).

- 13/11: análisis de los retos (agente de ideas, Claude); elegido Cala como principal; Nemotron y Codex como secundarios.
- 14/11: integración Claude → Codex (`cx`, perfiles por rol) para construir con Codex.
- 14/11: proyecto reorganizado para dos máquinas: backend/ + app/ (Expo), contrato docs/API.md, coordinación con `equipo` (claude-central).
- 14/11: canonizador de consultas a Cala (issue #9), construido con Codex: 4 variantes de una pregunta (con y sin acentos, inglés, catalán) dan la misma respuesta con 3 llamadas. Hallazgo: la Serie B de Amenitiz figura con 3.000 M EUR (cifra de reservas del artículo) y sin inversores enlazados.
- 14/11: canonizador fase 2 (plantillas fijas sobre knowledge_query): 8 variantes en 4 idiomas (2 preguntas) → la misma consulta exacta y la misma respuesta; 2 llamadas a Cala en vez de 8. Cruce con entidades marca la discrepancia de la Serie B de Amenitiz (3.000 M vs 38,9 M).
- 14/11: canonizador probado con 7 tipos de pregunta (fundadores, adquisiciones, financiación total, inversores, ejecutivos y listas de fintech y climate tech): 21 redacciones en 4 idiomas → 7 consultas, respuesta idéntica dentro de cada grupo. Corregido el formato de numerical_observations (Cala exige diccionario).
- 14/11: benchmark del canonizador (9 preguntas × 3 redacciones): directo 0/9 grupos consistentes y 27 llamadas; canonizado 9/9 y 9 llamadas en frío. Informe del error en docs/INFORME-ERROR-CALA.md y números en docs/BENCHMARK-CANONIZADOR.md.
- 14/11: benchmark con tercer modo (lenguaje natural directo a knowledge/query): también 0/9 grupos consistentes; cambian cifras, empresas y nombres de campo. Canonizador 9/9.
- 14/11: benchmark con agente conectado por MCP a Cala (Codex): 1/9 preguntas consistentes; usa siempre knowledge_search, reescribe la pregunta (24 textos distintos en 25 llamadas) y en 2 de 27 no consultó a Cala.
- 14/11: benchmark con agente por MCP con la guía de Cala cargada: usa consulta estructurada y entidades, pero 0/9 preguntas consistentes; con guía no inventa cuando el MCP falla (8 de 33 conexiones fallidas).
- 14/11: cambio de enfoque a 'Cala en el centro' (router, tablas de Cala, verificación de afirmaciones, journal); plan en docs/PLAN-CALA-CENTRO.md, contrato actualizado, README y documentación reescritos, registro de Codex en docs/CODEX.md.
- 14/11: roles fijados: Claude orquesta y diseña (no escribe código), Codex programa, Gemini es la IA del producto. Gemini reemplaza a NVIDIA; modelos elegidos midiendo la tarea del router (gemini-3.5-flash-lite: ~1 s, 3/3). Caché compartida en Aiven Valkey mergeada (#42).
