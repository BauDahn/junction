import asyncio
import json

from core.llm import make_llm
from . import handle_message


class DemoCala:
    async def entities(self, name, entity_type): return []
    async def introspection(self, entity_id): return {}
    async def retrieve(self, entity_id, **kwargs): return {}
    async def search(self, input): return {"answer": "", "sources": []}
    async def knowledge_query(self, input): return {"results": []}


async def main():
    llm, _ = make_llm()
    samples = ["¿Quién invirtió en Mews?", "Mews levantó 50 millones de euros.",
               "Me interesan fintech nórdicas en seed.",
               "Somos Stayflow en Barcelona y quiero saber quién invirtió en Mews."]
    for text in samples:
        result = await handle_message(text, {}, llm, cala=DemoCala())
        print(json.dumps({"message": text, **result}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
