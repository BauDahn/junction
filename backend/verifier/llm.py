import asyncio
import base64
import hashlib
import json
import os
import shutil
import tempfile
from pathlib import Path

import httpx

from .config import settings


def parse_json(text):
    if isinstance(text, dict):
        return text
    value = text.strip()
    if value.startswith("```"):
        value = value.strip("`")
        if value.startswith("json"):
            value = value[4:].strip()
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        start = value.find("{")
        if start < 0:
            raise ValueError("LLM response did not contain a JSON object")
        decoder = json.JSONDecoder()
        return decoder.raw_decode(value[start:])[0]


class NvidiaProvider:
    def __init__(self, api_key=None, model=None, client=None):
        self.api_key = api_key if api_key is not None else settings.nvidia_api_key
        self.model = model or settings.nvidia_model
        self.client = client

    async def complete_json(self, system, user, schema, images=None):
        content = [{"type": "text", "text": user}]
        for image in images or []:
            content.append({"type": "image_url", "image_url": {"url": "data:image/png;base64," + base64.b64encode(image).decode()}})
        owns = self.client is None
        client = self.client or httpx.AsyncClient(timeout=180)
        try:
            for attempt in range(3):
                response = await client.post("https://integrate.api.nvidia.com/v1/chat/completions",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    json={"model": self.model, "messages": [{"role": "system", "content": system}, {"role": "user", "content": content}], "response_format": {"type": "json_object"}})
                if response.status_code != 429 and response.status_code < 500:
                    break
                if attempt < 2:
                    await asyncio.sleep(2 ** attempt)
            response.raise_for_status()
            return parse_json(response.json()["choices"][0]["message"]["content"])
        finally:
            if owns:
                await client.aclose()


def strict_schema(schema):
    schema = json.loads(json.dumps(schema))
    def visit(node):
        if isinstance(node, dict):
            if node.get("type") == "object":
                node["additionalProperties"] = False
                node["required"] = list(node.get("properties", {}))
            for child in node.values():
                visit(child)
        elif isinstance(node, list):
            for child in node:
                visit(child)
    visit(schema)
    return schema


class CodexProvider:
    def __init__(self, timeout=None):
        self.timeout = float(timeout if timeout is not None else os.getenv("CODEX_TIMEOUT", "420"))

    async def complete_json(self, system, user, schema, images=None):
        binary = shutil.which("codex")
        if not binary:
            import glob
            candidates = glob.glob(str(Path.home() / ".nvm/versions/node/*/bin/codex"))
            binary = candidates[-1] if candidates else None
        if not binary:
            raise RuntimeError("No se encontró el ejecutable codex")
        with tempfile.TemporaryDirectory(prefix="deck-verifier-") as tmp:
            root = Path(tmp)
            schema_path, output = root / "schema.json", root / "out.json"
            schema_path.write_text(json.dumps(strict_schema(schema)))
            args = [binary, "exec", "--skip-git-repo-check", "--ephemeral", "-s", "read-only", "-m", "gpt-6-luna", "-c", 'model_reasoning_effort="low"', "--output-schema", str(schema_path), "-o", str(output)]
            for i, image in enumerate(images or []):
                image_path = root / f"image-{i}.png"
                image_path.write_bytes(image)
                args.extend(["-i", str(image_path)])
            args.append(system + "\n\n" + user)
            # stdin cerrado: si el servidor corre sin terminal, codex exec se queda esperando entrada.
            proc = await asyncio.create_subprocess_exec(*args, cwd=tmp, stdin=asyncio.subprocess.DEVNULL,
                                                        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
            try:
                stdout, stderr = await asyncio.wait_for(proc.communicate(), self.timeout)
            except asyncio.TimeoutError:
                proc.kill(); await proc.wait()
                raise RuntimeError(f"Codex excedió el timeout de {self.timeout:g} segundos")
            if proc.returncode:
                raise RuntimeError("codex exec falló: " + stderr.decode(errors="replace")[-1200:])
            result = output.read_text() if output.exists() else stdout.decode()
            return parse_json(result)


class ClaudeProvider:
    async def complete_json(self, system, user, schema, images=None):
        if images:
            raise RuntimeError("ClaudeProvider solo admite texto")
        binary = shutil.which("claude")
        if not binary:
            raise RuntimeError("No se encontró el ejecutable claude")
        proc = await asyncio.create_subprocess_exec(binary, "-p", "--output-format", "json", system + "\n\n" + user,
                                                    stdin=asyncio.subprocess.DEVNULL,
                                                    stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        stdout, stderr = await asyncio.wait_for(proc.communicate(), 180)
        if proc.returncode:
            raise RuntimeError("claude falló: " + stderr.decode(errors="replace")[-1200:])
        return parse_json(json.loads(stdout)["result"])


class CachedLLM:
    def __init__(self, provider, name, cache_dir):
        self.provider, self.name, self.cache_dir = provider, name, Path(cache_dir)

    async def complete_json(self, system, user, schema, images=None):
        digest = hashlib.sha256(self.name.encode() + system.encode() + user.encode() + b"".join(images or [])).hexdigest()
        path = self.cache_dir / "llm" / f"{digest}.json"
        if path.exists():
            return json.loads(path.read_text())
        result = await self.provider.complete_json(system, user, schema, images)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(result, ensure_ascii=False))
        return result


def make_llm(provider=None):
    name = provider or settings.llm_provider
    implementation = {"nvidia": NvidiaProvider, "codex": CodexProvider, "claude": ClaudeProvider}[name]()
    model = settings.nvidia_model if name == "nvidia" else ("gpt-6-luna" if name == "codex" else "claude")
    return CachedLLM(implementation, f"{name}:{model}", settings.cache_dir), model
