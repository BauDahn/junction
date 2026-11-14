"""Benchmark con un agente conectado al servidor MCP de Cala.

Un agente (Codex CLI) recibe la pregunta tal cual, con el MCP de Cala (https://api.cala.ai/mcp/) como única
herramienta, y decide solo qué herramientas llamar. Es como usaría Cala un usuario desde Claude Desktop o Codex.

  uv run python bench_mcp.py        # reanudable; escribe bench/results_mcp.json

La clave se lee de backend/.env y se pasa al proceso de Codex como variable de entorno (CALA_API_KEY);
el header X-API-KEY lo arma Codex con `env_http_headers`. Nunca se imprime ni se guarda.
"""
import glob, json, os, subprocess, sys, tempfile, time
from pathlib import Path

HERE = Path(__file__).parent
# --guia: carga la guía oficial de Cala (docs/CALA-SKILL.md, copia de github.com/cala-ai/cala-skill) en el prompt.
GUIA = "--guia" in sys.argv
OUT = HERE / "bench" / ("results_mcp_guia.json" if GUIA else "results_mcp.json")
GUIA_TEXTO = ""
if GUIA:
    GUIA_TEXTO = "\n".join(l for l in (HERE.parent / "docs" / "CALA-SKILL.md").read_text().splitlines()
                           if not l.startswith("<!--"))
ENV_FILE = HERE.parent / "backend" / ".env"
MODEL, EFFORT = "gpt-6-luna", "low"
PAUSA = 20  # segundos entre preguntas: el agente puede hacer varias llamadas y Cala limita (429)

SCHEMA = {"type": "object", "additionalProperties": False, "required": ["answer", "names", "amounts"],
          "properties": {"answer": {"type": "string"},
                         "names": {"type": "array", "items": {"type": "string"}},
                         "amounts": {"type": "array", "items": {"type": "string"}}}}
PROMPT = ("Use only the Cala MCP tools to answer the user's question. Do not use your own knowledge. "
          "Reply in English. In 'names' list the companies or people that answer the question, and in 'amounts' "
          "the money figures you report, exactly as you write them in 'answer'.\n\nUser question: ")
if GUIA:
    PROMPT = ("Follow this official guide for using Cala's tools:\n\n=== CALA GUIDE ===\n" + GUIA_TEXTO
              + "\n=== END OF GUIDE ===\n\n" + PROMPT)


def entorno():
    env = dict(os.environ)
    for line in ENV_FILE.read_text().splitlines():
        if line.startswith("CALA_API_KEY="):
            env["CALA_API_KEY"] = line.split("=", 1)[1].strip()
    if not env.get("CALA_API_KEY"):
        sys.exit("bench_mcp: falta CALA_API_KEY en backend/.env")
    bins = sorted(glob.glob(os.path.expanduser("~/.nvm/versions/node/*/bin")))
    if bins:
        env["PATH"] = bins[-1] + ":" + env["PATH"]
    return env


def agente(pregunta, env):
    with tempfile.TemporaryDirectory(prefix="bench-mcp-") as td:
        schema, out = Path(td, "schema.json"), Path(td, "out.json")
        schema.write_text(json.dumps(SCHEMA))
        cmd = ["codex", "exec", "--json", "--ephemeral", "--skip-git-repo-check", "-s", "read-only", "-m", MODEL,
               "-c", f'model_reasoning_effort="{EFFORT}"',
               "-c", 'mcp_servers.cala.url="https://api.cala.ai/mcp/"',
               "-c", 'mcp_servers.cala.env_http_headers={"X-API-KEY"="CALA_API_KEY"}',
               "--output-schema", str(schema), "-o", str(out), PROMPT + pregunta]
        t = time.monotonic()
        p = subprocess.run(cmd, cwd=td, env=env, capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=600)
        seg = round(time.monotonic() - t, 1)
        tools = []
        for line in p.stdout.splitlines():
            try:
                ev = json.loads(line)
            except ValueError:
                continue
            it = ev.get("item") or {}
            if ev.get("type") == "item.completed" and it.get("type") == "mcp_tool_call":
                tools.append({"tool": it.get("tool"), "arguments": it.get("arguments"), "status": it.get("status"),
                              "error": str(it.get("error"))[:200] if it.get("error") else None})
        final = json.loads(out.read_text()) if out.exists() and out.read_text().strip() else None
        return {"final": final, "tools": tools, "seconds": seg, "exit": p.returncode,
                "error": None if final else (p.stderr or "")[-400:]}


def main():
    env = entorno()
    groups = json.loads((HERE / "bench" / "questions.json").read_text())
    results = json.loads(OUT.read_text()) if OUT.exists() else {}
    for group in groups:
        g = results.setdefault(group["group"], {})
        for q in group["questions"]:
            if q in g and g[q].get("final"):
                continue
            try:
                g[q] = agente(q, env)
            except Exception as exc:  # no cortar el benchmark por una pregunta
                g[q] = {"final": None, "tools": [], "error": str(exc)[:300]}
            OUT.write_text(json.dumps(results, ensure_ascii=False, indent=1))
            print("mcp", q[:60], g[q].get("seconds", "ERR"), [t["tool"] for t in g[q]["tools"]], file=sys.stderr, flush=True)
            time.sleep(PAUSA)
    print(OUT)


if __name__ == "__main__":
    main()
