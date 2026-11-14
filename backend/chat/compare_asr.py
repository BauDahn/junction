"""Compare production Gemini audio prompts/models and local Whisper."""
import argparse
import asyncio
import time
from pathlib import Path

from core.config import settings
from core.llm import GeminiProvider
from . import transcribe


def cell(value):
    return str(value or "").replace("|", "\\|").replace("\r", " ").replace("\n", " ")


async def compare(paths, hint=None):
    models = [settings.gemini_fast_model, "gemini-3.5-transcribe"]
    if transcribe.whisper_available(): models.append("whisper local")
    print("| audio | modelo | segundos | transcript | text |")
    print("|---|---|---:|---|---|")
    for path in paths:
        for model in models:
            started = time.perf_counter()
            try:
                if model == "whisper local":
                    result = await asyncio.to_thread(transcribe._whisper_transcribe, path, hint)
                else:
                    llm = GeminiProvider(model=model)
                    user = "Transcribe and clean the attached audio."
                    if hint: user += f" Known proper names (preserve spelling exactly): {hint}"
                    result = await llm.complete_json(transcribe.SYSTEM, user, transcribe.SCHEMA,
                                                     audio=(path.read_bytes(), transcribe.mime_for(path)))
                seconds = time.perf_counter() - started
                print(f"| {cell(path.name)} | {cell(model)} | {seconds:.2f} | {cell(result.get('transcript'))} | {cell(result.get('text'))} |")
            except Exception as exc:
                seconds = time.perf_counter() - started
                message = str(exc).splitlines()[0][:160] or type(exc).__name__
                print(f"| {cell(path.name)} | {cell(model)} | {seconds:.2f} | {cell('ERROR: ' + message)} |  |")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("audio", nargs="+", type=Path)
    parser.add_argument("--hint")
    args = parser.parse_args()
    asyncio.run(compare(args.audio, args.hint))


if __name__ == "__main__":
    main()
