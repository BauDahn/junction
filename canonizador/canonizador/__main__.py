import asyncio
import json
import sys

from .api import answer

if __name__ == "__main__":
    if len(sys.argv) < 2: raise SystemExit('Uso: uv run python -m canonizador "pregunta"')
    print(json.dumps(asyncio.run(answer(" ".join(sys.argv[1:]))), ensure_ascii=False, indent=2))
