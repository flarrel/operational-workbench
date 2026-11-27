"""Loopback-only HTTP interface for the analytics and drafting workflow."""

from datetime import date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import re
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from .data import FIRST, LAST, SITES, evidence, snapshot, source_record
from .handoff import render_report, workflow
from .prompts import BY_ID, PROMPTS, DraftError, generate, messages

STATIC = Path(__file__).with_name("static")
FILES = {
    "/": ("index.html", "text/html"),
    "/static/app.js": ("app.js", "text/javascript"),
    "/static/style.css": ("style.css", "text/css"),
}


def filters(values: dict) -> tuple[str, date, date]:
    site = values.get("site", "Semua")
    if site not in ("Semua", *SITES):
        raise ValueError("Lokasi tidak dikenal.")
    try:
        start = date.fromisoformat(values.get("start", FIRST.isoformat()))
        end = date.fromisoformat(values.get("end", LAST.isoformat()))
    except (TypeError, ValueError) as error:
        raise ValueError("Gunakan tanggal berformat YYYY-MM-DD.") from error
    if start > end:
        raise ValueError("Tanggal mulai harus sebelum atau sama dengan tanggal akhir.")
    return site, start, end


def handler_for(database: Path, evaluation: Path):
    class Handler(BaseHTTPRequestHandler):
        def respond(self, status: int, body: bytes, content_type: str):
            self.send_response(status)
            self.send_header("Content-Type", f"{content_type}; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'self' 'unsafe-inline'; object-src 'none'; frame-ancestors 'none'")
            self.end_headers()
            self.wfile.write(body)

        def json(self, status: int, data):
            self.respond(status, json.dumps(data, ensure_ascii=False).encode(), "application/json")

        def do_GET(self):
            url = urlsplit(self.path)
            if url.path in FILES:
                filename, media_type = FILES[url.path]
                self.respond(200, (STATIC / filename).read_bytes(), media_type)
            elif url.path == "/api/prompts":
                self.json(200, [
                    {**prompt, "template": messages(prompt["id"], "[arahan]", {}, "refined")[0]["content"]
                     + "\n\nPermintaan: [arahan]\nSumber yang tersedia: [tempel fakta dengan ID sumber]"}
                    for prompt in PROMPTS
                ])
            elif url.path == "/api/source":
                try:
                    row_id = int(parse_qs(url.query).get("id", [""])[-1])
                except ValueError:
                    self.json(400, {"error": "ID sumber harus berupa angka."})
                    return
                if not 0 < row_id < 2**63:
                    self.json(400, {"error": "ID sumber di luar rentang."})
                    return
                row = source_record(database, row_id)
                if row:
                    self.json(200, row)
                else:
                    self.json(404, {"error": "Sumber tidak ditemukan."})
            elif url.path == "/api/dashboard":
                try:
                    values = {key: items[-1] for key, items in parse_qs(url.query).items()}
                    self.json(200, snapshot(database, *filters(values)))
                except ValueError as error:
                    self.json(400, {"error": str(error)})
            elif url.path in ("/api/workflow", "/status", "/briefing"):
                dataset = snapshot(database, "Semua", FIRST, LAST)
                if url.path == "/api/workflow":
                    self.json(200, workflow(dataset))
                    return
                report = json.loads(evaluation.read_text()) if evaluation.is_file() else None
                page = render_report(dataset, report, briefing=url.path == "/briefing")
                self.respond(200, page.encode(), "text/html")
            else:
                self.json(404, {"error": "Halaman tidak ditemukan."})

        def do_POST(self):
            if self.path != "/api/draft":
                self.json(404, {"error": "Halaman tidak ditemukan."})
                return
            if self.headers.get_content_type() != "application/json":
                self.json(415, {"error": "Gunakan JSON."})
                return
            try:
                size = int(self.headers.get("Content-Length", "0"))
                if not 0 < size <= 8192:
                    raise ValueError("Ukuran permintaan tidak valid.")
                values = json.loads(self.rfile.read(size))
                if not isinstance(values, dict):
                    raise ValueError("Permintaan harus berupa objek JSON.")
                prompt = values.get("prompt")
                brief = values.get("brief", "")
                if not isinstance(prompt, str) or prompt not in BY_ID:
                    raise ValueError("Pilih prompt dari bank prompt.")
                if not isinstance(brief, str) or len(brief.strip()) > 1000:
                    raise ValueError("Arahan dapat berisi hingga 1.000 karakter.")
                dataset = snapshot(database, *filters(values))
                if dataset["totals"]["days"] == 0:
                    self.json(422, {"error": "Tidak ada data pada filter ini."})
                    return
                facts = evidence(dataset)
                selected = values.get("source", "")
                if not isinstance(selected, str):
                    raise ValueError("Pilih ID sumber yang valid.")
                if selected:
                    if selected not in facts:
                        raise ValueError("Sumber tidak ada dalam cakupan filter aktif.")
                    facts = {selected: facts[selected]}
                draft = generate(prompt, brief.strip() or BY_ID[prompt]["example"], facts)
                cited = set(re.findall(r"\[([A-Z][A-Z0-9]*)\]", draft))
                self.json(200, {
                    "text": draft, "evidence": facts,
                    "has_valid_citations": bool(cited) and cited <= facts.keys(),
                })
            except (UnicodeDecodeError, json.JSONDecodeError):
                self.json(400, {"error": "Format JSON tidak valid."})
            except ValueError as error:
                self.json(400, {"error": str(error)})
            except DraftError as error:
                self.json(503, {"error": str(error)})

    return Handler


def serve_app(database: Path, evaluation: Path, port: int):
    with ThreadingHTTPServer(("127.0.0.1", port), handler_for(database, evaluation)) as server:
        print(f"http://127.0.0.1:{port}", flush=True)
        server.serve_forever()
