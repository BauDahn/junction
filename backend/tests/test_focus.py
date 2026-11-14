import asyncio
from chat.focus import focus_table


class PickLLM:
    def __init__(self, rows): self.rows, self.calls = rows, 0
    async def complete_json(self, system, user, schema):
        self.calls += 1
        return {"rows": self.rows}


def table(n):
    return {"type": "cala_table", "columns": ["name", "title"], "rows": [[f"P{i}", f"T{i}"] for i in range(n)], "sources": []}


def test_single_row_gives_answer_from_cala_cells():
    block = asyncio.run(focus_table("who is the CEO?", table(21), PickLLM([1])))
    assert block["focus_rows"] == [1] and block["answer"] == "P1 · T1"
    assert len(block["rows"]) == 21  # la tabla completa se conserva


def test_invalid_indices_fall_back_to_first_rows():
    block = asyncio.run(focus_table("investors?", table(8), PickLLM([99, -1, True])))
    assert block["focus_rows"] == [0, 1, 2, 3, 4] and "answer" not in block


def test_small_tables_skip_the_model():
    llm = PickLLM([0])
    block = asyncio.run(focus_table("x", table(2), llm))
    assert llm.calls == 0 and block["focus_rows"] == [0, 1]
