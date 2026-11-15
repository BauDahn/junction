import asyncio
import json
import os
import shutil
import tempfile
import glob
import re
from pathlib import Path

from .cache import load_env

load_env()

SECTORS = ["hotel technology", "fintech", "healthtech", "climate tech", "saas", "ai", "cybersecurity", "edtech", "proptech", "mobility", "foodtech", "biotech", "ecommerce", "logistics", "gaming", "other"]
SCHEMA = {"type": "object", "properties": {"entities": {"type": "array", "items": {"type": "object", "properties": {"name": {"type": "string"}, "type": {"type": "string", "enum": ["Company", "Person", "Event", "Investor"]}}, "required": ["name", "type"]}}, "attribute": {"type": "string", "enum": ["funding_round", "total_funding", "investors", "lead_investors", "founders", "executives", "headcount", "acquisitions", "profile", "event_attendees", "company_list", "other"]}, "filters": {"type": "object", "properties": {"round_label": {"type": ["string", "null"]}, "year": {"type": ["integer", "null"]}, "location": {"type": ["string", "null"]}, "sector": {"type": ["string", "null"], "enum": [None, *SECTORS]}, "min_funding": {"type": ["integer", "null"]}}}}, "required": ["entities", "attribute", "filters"]}
SYSTEM = """Convert the user question to the required JSON intent. Preserve proper names exactly as written. Use Cala round codes such as SERIES_B. Return only schema-conforming JSON.

Company discovery rule: if the user asks for a LIST of companies/startups selected by criteria (location, sector, minimum funding, round) and names no specific company, set attribute=company_list and entities=[]. Do not use total_funding for this request. Example: 'List Spanish hotel-tech startups that raised at least 10 million' → company_list, location='Spain', sector='hotel technology', min_funding=10000000.

Always return list filters in canonical English regardless of question language: location is a country/city name in English and Title Case (España → Spain); sector is one lowercase singular enum value; min_funding is an integer in the base currency (10M / 10 millones → 10000000). Examples: 'startups españolas de tecnología hotelera con 10 millones' → location='Spain', sector='hotel technology', min_funding=10000000; 'hotel tech startups in Spain with 10000000 funding' → the same values."""


def parse_json(text):
    if isinstance(text, dict): return text
    text = text.strip()
    if text.startswith("```"): text = text.strip("` \n").removeprefix("json").strip()
    try: return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        if start < 0: raise ValueError("LLM response did not contain JSON")
        return json.JSONDecoder().raw_decode(text[start:])[0]


def strict_schema(schema):
    """Returns a copy compatible with strict-mode Structured Outputs."""
    schema = json.loads(json.dumps(schema))

    def visit(node):
        if isinstance(node, dict):
            if node.get("type") == "object":
                properties = node.get("properties", {})
                node["additionalProperties"] = False
                node["required"] = list(properties)
            for value in node.values():
                visit(value)
        elif isinstance(node, list):
            for value in node:
                visit(value)

    visit(schema)
    return schema


class CodexProvider:
    def __init__(self, model="gpt-5.6-luna", effort="low", timeout=120):
        self.model, self.effort, self.timeout = model, effort, timeout

    async def complete_json(self, system, user, schema):
        binary = shutil.which("codex")
        if not binary:
            candidates = glob.glob(str(Path.home() / ".nvm/versions/node/*/bin/codex"))
            binary = candidates[-1] if candidates else None
        if not binary: raise RuntimeError("codex executable was not found")
        with tempfile.TemporaryDirectory(prefix="cala-intent-") as td:
            root = Path(td); sp, out = root / "schema.json", root / "out.json"
            sp.write_text(json.dumps(strict_schema(schema)))
            proc = await asyncio.create_subprocess_exec(binary, "exec", "--skip-git-repo-check", "--ephemeral", "-s", "read-only", "-m", self.model, "-c", f'model_reasoning_effort="{self.effort}"', "--output-schema", str(sp), "-o", str(out), system + "\n\n" + user, cwd=td, stdin=asyncio.subprocess.DEVNULL, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
            try: stdout, stderr = await asyncio.wait_for(proc.communicate(), self.timeout)
            except asyncio.TimeoutError:
                proc.kill()
                _, stderr = await proc.communicate()
                detail = stderr.decode(errors="replace")[-800:]
                raise RuntimeError(f"codex exec timed out after {self.timeout:g} seconds" + (f": {detail}" if detail else ""))
            if proc.returncode: raise RuntimeError("codex exec failed: " + stderr.decode(errors="replace")[-800:])
            return parse_json(out.read_text() if out.exists() else stdout.decode())


class NvidiaProvider:
    def __init__(self, api_key=None, model=None):
        self.api_key = api_key or os.getenv("NVIDIA_API_KEY", "")
        self.model = model or os.getenv("NVIDIA_MODEL", "nvidia/nemotron-3.5-super-vl")

    async def complete_json(self, system, user, schema):
        import httpx
        async with httpx.AsyncClient(timeout=120) as client:
            for attempt in range(3):
                r = await client.post("https://integrate.api.nvidia.com/v1/chat/completions", headers={"Authorization": f"Bearer {self.api_key}"}, json={"model": self.model, "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}], "response_format": {"type": "json_object"}})
                if r.status_code != 429 and r.status_code < 500: break
                if attempt < 2: await asyncio.sleep(2 ** attempt)
            r.raise_for_status()
            return parse_json(r.json()["choices"][0]["message"]["content"])


class GeminiProvider:
    def __init__(self, api_key=None, model=None, client=None):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY", "")
        self.model = model or os.getenv("GEMINI_FAST_MODEL", "gemini-3.5-flash-lite")
        self.client = client

    async def complete_json(self, system, user, schema):
        if not self.api_key: raise RuntimeError("Falta GEMINI_API_KEY (o GOOGLE_API_KEY)")
        import httpx
        def gemini_schema(value):
            value = json.loads(json.dumps(value))
            def visit(node):
                if isinstance(node, dict):
                    node.pop("additionalProperties", None)
                    kind = node.get("type")
                    if isinstance(kind, list):
                        remaining = [item for item in kind if item != "null"]
                        if "null" in kind: node["nullable"] = True
                        node["type"] = remaining[0] if len(remaining) == 1 else "string"
                    for child in node.values(): visit(child)
                elif isinstance(node, list):
                    for child in node: visit(child)
            visit(value)
            return value
        owns = self.client is None
        client = self.client or httpx.AsyncClient(timeout=60)
        try:
            for attempt in range(3):
                r = await client.post(f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent", headers={"x-goog-api-key": self.api_key}, json={"systemInstruction": {"parts": [{"text": system}]}, "contents": [{"role": "user", "parts": [{"text": user}]}], "generationConfig": {"responseMimeType": "application/json", "responseSchema": gemini_schema(schema), "temperature": 0}})
                if r.status_code != 429 and r.status_code < 500: break
                if attempt < 2: await asyncio.sleep(2 ** attempt)
            try: r.raise_for_status()
            except httpx.HTTPStatusError as exc:
                try: message = exc.response.json().get("error", {}).get("message", "")
                except (ValueError, AttributeError, TypeError): message = ""
                message = str(message or "Unspecified error").replace(self.api_key, "[redacted]")
                message = re.sub(r"https?://\S+", "[URL omitted]", message)
                raise RuntimeError(f"Gemini returned HTTP {exc.response.status_code}: {message[:300]}") from None
            return parse_json(r.json()["candidates"][0]["content"]["parts"][0]["text"])
        finally:
            if owns: await client.aclose()


class IntentParser:
    def __init__(self, provider=None, cache=None):
        provider_name = os.getenv("LLM_PROVIDER", "").lower()
        if not provider_name:
            provider_name = "gemini" if (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")) else ("nvidia" if os.getenv("NVIDIA_API_KEY") else "codex")
        self.provider = provider or ({"nvidia": NvidiaProvider, "gemini": GeminiProvider, "codex": CodexProvider}[provider_name]())
        self.cache = cache

    async def parse(self, question):
        key = {"system": SYSTEM, "question": question}
        cached = self.cache.get("intents", key) if self.cache else None
        if cached is not None: return cached
        result = await self.provider.complete_json(SYSTEM, question, SCHEMA)
        result.setdefault("filters", {})
        if self.cache: self.cache.put("intents", key, result)
        return result
