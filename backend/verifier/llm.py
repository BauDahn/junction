import asyncio
import base64
import hashlib
import json
import os
import re
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

    async def complete_json(self, system, user, schema, images=None, audio=None):
        if audio: raise RuntimeError("NvidiaProvider no admite audio")
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


def gemini_schema(schema):
    """Convierte JSON Schema al subconjunto admitido por Gemini."""
    schema = json.loads(json.dumps(schema))
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
    visit(schema)
    return schema


def _gemini_http_error(response, api_key):
    try:
        message = response.json().get("error", {}).get("message", "")
    except (ValueError, AttributeError, TypeError):
        message = ""
    message = str(message or "Error sin detalle")
    if api_key: message = message.replace(api_key, "[redactado]")
    message = re.sub(r"https?://\S+", "[URL omitida]", message)
    return f"Gemini respondió HTTP {response.status_code}: {message[:300]}"


class GeminiProvider:
    def __init__(self, api_key=None, model=None, client=None):
        self.api_key = api_key if api_key is not None else settings.gemini_api_key
        self.model = model or settings.gemini_model
        self.client = client

    async def complete_json(self, system, user, schema, images=None, audio=None):
        if not self.api_key: raise RuntimeError("Falta GEMINI_API_KEY (o GOOGLE_API_KEY)")
        parts = [{"text": user}]
        for image in images or []:
            parts.append({"inlineData": {"mimeType": "image/png", "data": base64.b64encode(image).decode()}})
        if audio:
            data, mime_type = audio
            parts.append({"inlineData": {"mimeType": mime_type, "data": base64.b64encode(data).decode()}})
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"
        owns = self.client is None
        client = self.client or httpx.AsyncClient(timeout=60)
        try:
            for attempt in range(3):
                response = await client.post(url, headers={"x-goog-api-key": self.api_key}, json={
                    "systemInstruction": {"parts": [{"text": system}]},
                    "contents": [{"role": "user", "parts": parts}],
                    "generationConfig": {"responseMimeType": "application/json", "responseSchema": gemini_schema(schema), "temperature": 0},
                })
                if response.status_code != 429 and response.status_code < 500: break
                if attempt < 2: await asyncio.sleep(2 ** attempt)
            response.raise_for_status()
            return parse_json(response.json()["candidates"][0]["content"]["parts"][0]["text"])
        except httpx.HTTPStatusError as exc:
            raise RuntimeError(_gemini_http_error(exc.response, self.api_key)) from None
        finally:
            if owns: await client.aclose()


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

    async def complete_json(self, system, user, schema, images=None, audio=None):
        if audio: raise RuntimeError("CodexProvider no admite audio")
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
    async def complete_json(self, system, user, schema, images=None, audio=None):
        if audio: raise RuntimeError("ClaudeProvider no admite audio")
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

    async def complete_json(self, system, user, schema, images=None, audio=None):
        audio_bytes = audio[0] if audio else b""
        digest = hashlib.sha256(self.name.encode() + system.encode() + user.encode() + b"".join(images or []) + audio_bytes).hexdigest()
        path = self.cache_dir / "llm" / f"{digest}.json"
        if path.exists():
            return json.loads(path.read_text())
        result = await (self.provider.complete_json(system, user, schema, images, audio=audio) if audio else self.provider.complete_json(system, user, schema, images))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(result, ensure_ascii=False))
        return result


def make_llm(provider=None, tier='strong'):
    name = provider or settings.llm_provider
    model = (settings.gemini_fast_model if tier == "fast" else settings.gemini_model) if name == "gemini" else (settings.nvidia_model if name == "nvidia" else ("gpt-6-luna" if name == "codex" else "claude"))
    implementation = {"nvidia": NvidiaProvider, "gemini": lambda: GeminiProvider(model=model), "codex": CodexProvider, "claude": ClaudeProvider}[name]()
    return CachedLLM(implementation, f"{name}:{model}", settings.cache_dir), model
