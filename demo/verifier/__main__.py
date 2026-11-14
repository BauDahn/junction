import argparse
import asyncio
import json
from pathlib import Path
import sys

from .pipeline import verify_pdf


def main():
    parser = argparse.ArgumentParser(description="Verify public claims in a pitch deck using Cala")
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--provider", choices=["nvidia", "codex", "claude"])
    args = parser.parse_args()
    try:
        def progress(stage, done, total):
            if stage == "extracting":
                message = "Extracting claims"
            elif stage == "checking":
                message = f"Checking with Cala {done}/{total}"
            else:
                message = f"Judging batches {done}/{total}"
            print(message, file=sys.stderr, flush=True)
        report = asyncio.run(verify_pdf(args.pdf, args.provider, on_progress=progress))
        print(json.dumps(report, ensure_ascii=False, indent=2))
    except Exception as exc:
        parser.exit(1, f"Error al verificar deck: {exc}\n")


if __name__ == "__main__":
    main()
