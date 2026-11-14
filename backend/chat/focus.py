"""Recorta una tabla de Cala a las filas que responden la pregunta.

El modelo solo elige índices de filas; la respuesta se arma con las celdas de Cala tal cual,
así nunca escribe nombres ni cifras propias.
"""
import json

SCHEMA = {"type": "object", "additionalProperties": False, "required": ["rows"],
          "properties": {"rows": {"type": "array", "items": {"type": "integer"}}}}

SYSTEM = ("You get a user question and a table returned by a database. Return the zero-based indices of the rows "
          "that directly answer the question, most relevant first. If the question asks for one specific thing "
          "(e.g. 'who is the CEO'), return only the row(s) that match it. If it asks for a list, return the rows "
          "that belong to the list, at most 10. If no row answers it, return an empty list. Never invent rows.")

MAX_LIST = 10


def answer_line(columns, row):
    cells = [str(v) for v in row if v not in (None, "")]
    return " · ".join(cells)


async def focus_table(question, block, llm):
    rows = block.get("rows") or []
    if len(rows) <= 3:
        block["focus_rows"] = list(range(len(rows)))
    else:
        table = {"columns": block.get("columns"), "rows": [[i, *r] for i, r in enumerate(rows)]}
        user = json.dumps({"question": question, "table": table}, ensure_ascii=False)
        try:
            result = await llm.complete_json(SYSTEM, user, SCHEMA)
            picked = [i for i in result.get("rows", []) if isinstance(i, int) and not isinstance(i, bool) and 0 <= i < len(rows)]
        except Exception:
            picked = []
        block["focus_rows"] = list(dict.fromkeys(picked))[:MAX_LIST] or list(range(min(5, len(rows))))
    if len(block["focus_rows"]) == 1:
        block["answer"] = answer_line(block.get("columns"), rows[block["focus_rows"][0]])
    return block
