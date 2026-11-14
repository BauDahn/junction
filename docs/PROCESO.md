# Proceso y decisiones

Una línea por hito: fecha y hora, qué se decidió o construyó, con qué herramienta (Codex, Nemotron, Cala).

- 13/11: análisis de los retos (agente de ideas, Claude); elegido Cala como principal; Nemotron y Codex como secundarios.
- 14/11: integración Claude → Codex (`cx`, perfiles por rol) para construir con Codex.
- 14/11: proyecto reorganizado para dos máquinas: backend/ + app/ (Expo), contrato docs/API.md, coordinación con `equipo` (claude-central).
- 14/11: canonizador de consultas a Cala (issue #9), construido con Codex: 4 variantes de una pregunta (con y sin acentos, inglés, catalán) dan la misma respuesta con 3 llamadas. Hallazgo: la Serie B de Amenitiz figura con 3.000 M EUR (cifra de reservas del artículo) y sin inversores enlazados.
- 14/11: canonizador fase 2 (plantillas fijas sobre knowledge_query): 8 variantes en 4 idiomas (2 preguntas) → la misma consulta exacta y la misma respuesta; 2 llamadas a Cala en vez de 8. Cruce con entidades marca la discrepancia de la Serie B de Amenitiz (3.000 M vs 38,9 M).
