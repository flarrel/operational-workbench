import argparse
import json
import os
from pathlib import Path
import subprocess

from .data import generate


def main():
    parser = argparse.ArgumentParser(description="Asisten Operasional")
    default = Path(__file__).resolve().parents[2] / "internal" / "runtime"
    parser.add_argument("--runtime", type=Path, default=default, help="Data and model directory")
    command = parser.add_subparsers(dest="command", required=True)
    command.add_parser("init", help="Regenerate the synthetic operational database")
    command.add_parser("model", help="Start the local generation server")
    serve = command.add_parser("serve", help="Start the local dashboard")
    serve.add_argument("--port", type=int, default=8775)
    evaluate = command.add_parser("eval", help="Run and save paired prompt results")
    evaluate.add_argument("--output", type=Path)
    args = parser.parse_args()
    runtime = args.runtime.resolve()
    database = runtime / "ops.sqlite"
    if args.command == "init":
        generate(database)
        print(database)
    elif args.command == "model":
        binary = runtime / "llama" / "build" / "bin" / "llama-server"
        model = runtime / "model.gguf"
        if not binary.is_file() or not model.is_file():
            parser.error("The model and inference executable are required. See README.md.")
        subprocess.run(
            [str(binary), "--model", str(model), "--alias", "qwen3-4b",
             "--host", "127.0.0.1", "--port", "8776", "--ctx-size", "4096",
             "--parallel", "1", "--jinja", "--reasoning-budget", "0", "--no-webui"],
            env={**os.environ, "TMPDIR": str(runtime)}, check=True,
        )
    elif args.command == "serve":
        from .web import serve_app
        if not database.is_file():
            parser.error("Create the demo database with python3 -m ops init.")
        serve_app(database, runtime / "evaluation.json", args.port)
    elif args.command == "eval":
        from .evaluation import run
        output = args.output or runtime / "evaluation.json"
        report = run()
        output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
        print(json.dumps(report["summary"], ensure_ascii=False))
        print(output)
