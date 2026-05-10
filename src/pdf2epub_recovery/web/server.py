"""Small local web UI for pdf2epub-recovery."""

from __future__ import annotations

import json
import mimetypes
import tempfile
import threading
import uuid
import webbrowser
from dataclasses import dataclass, field
from html import escape
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

from pdf2epub_recovery.pipeline import ConversionError, convert_pdf_to_epub


@dataclass
class WebJob:
    job_id: str
    work_dir: Path
    input_path: Path
    output_path: Path
    report_path: Path
    output_name: str
    status: str = "queued"
    progress: int = 0
    logs: list[str] = field(default_factory=list)
    error: str | None = None

    def log(self, message: str) -> None:
        self.logs.append(message)

    def update(self, progress: int, message: str) -> None:
        self.progress = max(self.progress, progress)
        self.log(message)

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "job_id": self.job_id,
            "status": self.status,
            "progress": self.progress,
            "logs": self.logs,
            "error": self.error,
        }
        if self.status == "done":
            data["download_url"] = f"/api/jobs/{self.job_id}/download"
            data["report_url"] = f"/api/jobs/{self.job_id}/report"
        return data


class JobStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self._jobs: dict[str, WebJob] = {}
        self._lock = threading.Lock()

    def create(self, filename: str, content: bytes) -> WebJob:
        job_id = uuid.uuid4().hex
        work_dir = self.root / job_id
        work_dir.mkdir(parents=True, exist_ok=True)
        safe_name = _safe_filename(filename) or "input.pdf"
        input_path = work_dir / safe_name
        input_path.write_bytes(content)
        output_name = f"{Path(safe_name).stem or 'book'}.epub"
        job = WebJob(
            job_id=job_id,
            work_dir=work_dir,
            input_path=input_path,
            output_path=work_dir / output_name,
            report_path=work_dir / "quality-report.json",
            output_name=output_name,
        )
        with self._lock:
            self._jobs[job_id] = job
        return job

    def get(self, job_id: str) -> WebJob | None:
        with self._lock:
            return self._jobs.get(job_id)


def run_web_server(host: str = "127.0.0.1", port: int = 8765, open_browser: bool = True) -> None:
    """Run the local web UI until interrupted."""

    store = JobStore(Path(tempfile.gettempdir()) / "pdf2epub-recovery-web")
    handler = _make_handler(store)
    server = ThreadingHTTPServer((host, port), handler)
    url = f"http://{host}:{server.server_port}"
    print(f"pdf2epub-recovery web UI running at {url}")
    if open_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping web UI.")
    finally:
        server.server_close()


def _make_handler(store: JobStore):
    class WebHandler(BaseHTTPRequestHandler):
        server_version = "pdf2epub-recovery-web/0.1"

        def do_GET(self) -> None:
            path = urlparse(self.path).path
            if path == "/":
                self._send_html(INDEX_HTML)
                return
            if path == "/static/app.css":
                self._send_bytes(STYLE_CSS.encode("utf-8"), "text/css; charset=utf-8")
                return
            if path == "/static/app.js":
                self._send_bytes(APP_JS.encode("utf-8"), "application/javascript; charset=utf-8")
                return
            if path.startswith("/api/jobs/"):
                self._handle_job_get(path)
                return
            self._send_json({"error": "Not found."}, HTTPStatus.NOT_FOUND)

        def do_POST(self) -> None:
            path = urlparse(self.path).path
            if path != "/api/jobs":
                self._send_json({"error": "Not found."}, HTTPStatus.NOT_FOUND)
                return

            try:
                upload = self._read_upload()
            except ValueError as exc:
                self._send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
                return

            job = store.create(upload["filename"], upload["content"])
            job.log(f"Uploaded {upload['filename']}.")
            thread = threading.Thread(
                target=_run_job,
                args=(
                    job,
                    bool(upload["fields"].get("keep_artifacts")),
                    not bool(upload["fields"].get("no_dehyphenate")),
                    _parse_optional_int(upload["fields"].get("max_pages")),
                ),
                daemon=True,
            )
            thread.start()
            self._send_json(job.to_dict(), HTTPStatus.ACCEPTED)

        def log_message(self, format: str, *args: object) -> None:
            return

        def _handle_job_get(self, path: str) -> None:
            parts = [part for part in path.split("/") if part]
            if len(parts) < 3:
                self._send_json({"error": "Missing job id."}, HTTPStatus.BAD_REQUEST)
                return

            job = store.get(parts[2])
            if job is None:
                self._send_json({"error": "Unknown job."}, HTTPStatus.NOT_FOUND)
                return

            if len(parts) == 3:
                self._send_json(job.to_dict())
                return
            if len(parts) == 4 and parts[3] == "download":
                self._send_file(job.output_path, "application/epub+zip", job.output_name)
                return
            if len(parts) == 4 and parts[3] == "report":
                self._send_file(job.report_path, "application/json", "quality-report.json")
                return
            self._send_json({"error": "Not found."}, HTTPStatus.NOT_FOUND)

        def _read_upload(self) -> dict[str, Any]:
            content_type = self.headers.get("Content-Type", "")
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length)
            fields, files = _parse_multipart(content_type, body)
            file_item = files.get("pdf")
            if file_item is None or not file_item["content"]:
                raise ValueError("Please choose a PDF file.")
            return {
                "filename": file_item["filename"],
                "content": file_item["content"],
                "fields": fields,
            }

        def _send_html(self, html: str) -> None:
            self._send_bytes(html.encode("utf-8"), "text/html; charset=utf-8")

        def _send_json(self, payload: dict[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
            self._send_bytes(
                json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                "application/json; charset=utf-8",
                status,
            )

        def _send_file(self, path: Path, content_type: str, filename: str) -> None:
            if not path.exists():
                self._send_json({"error": "File is not available yet."}, HTTPStatus.NOT_FOUND)
                return
            guessed = mimetypes.guess_type(filename)[0]
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", content_type or guessed or "application/octet-stream")
            self.send_header("Content-Length", str(path.stat().st_size))
            self.send_header(
                "Content-Disposition",
                f'attachment; filename="{escape(filename, quote=True)}"',
            )
            self.end_headers()
            with path.open("rb") as handle:
                self.wfile.write(handle.read())

        def _send_bytes(
            self,
            content: bytes,
            content_type: str,
            status: HTTPStatus = HTTPStatus.OK,
        ) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)

    return WebHandler


def _run_job(job: WebJob, keep_artifacts: bool, dehyphenate: bool, max_pages: int | None) -> None:
    job.status = "running"
    job.update(1, "Starting conversion.")
    try:
        result = convert_pdf_to_epub(
            job.input_path,
            job.output_path,
            keep_artifacts=keep_artifacts,
            dehyphenate=dehyphenate,
            max_pages=max_pages,
            progress_callback=job.update,
        )
        job.report_path.write_text(
            json.dumps(result.report.to_dict(), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        job.status = "done"
        job.progress = 100
        job.log("EPUB and quality report are ready.")
    except ConversionError as exc:
        job.report_path.write_text(
            json.dumps(exc.report.to_dict(), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        job.status = "error"
        job.progress = max(job.progress, 100)
        job.error = str(exc)
        job.log(f"Conversion failed: {exc}")
    except Exception as exc:
        job.status = "error"
        job.progress = max(job.progress, 100)
        job.error = str(exc)
        job.log(f"Conversion failed: {exc}")


def _parse_multipart(
    content_type: str, body: bytes
) -> tuple[dict[str, str], dict[str, dict[str, Any]]]:
    if "multipart/form-data" not in content_type or "boundary=" not in content_type:
        raise ValueError("Expected multipart form upload.")
    boundary = content_type.split("boundary=", 1)[1].strip().strip('"')
    delimiter = f"--{boundary}".encode()
    fields: dict[str, str] = {}
    files: dict[str, dict[str, Any]] = {}

    for raw_part in body.split(delimiter):
        part = raw_part.strip(b"\r\n")
        if not part or part == b"--":
            continue
        header_blob, separator, content = part.partition(b"\r\n\r\n")
        if not separator:
            continue
        headers = _parse_part_headers(header_blob.decode("utf-8", errors="replace"))
        disposition = headers.get("content-disposition", "")
        name = _disposition_value(disposition, "name")
        if not name:
            continue
        content = content.removesuffix(b"\r\n")
        filename = _disposition_value(disposition, "filename")
        if filename is not None:
            files[name] = {"filename": filename, "content": content}
        else:
            fields[name] = content.decode("utf-8", errors="replace")
    return fields, files


def _parse_part_headers(header_blob: str) -> dict[str, str]:
    headers: dict[str, str] = {}
    for line in header_blob.splitlines():
        key, separator, value = line.partition(":")
        if separator:
            headers[key.strip().lower()] = value.strip()
    return headers


def _disposition_value(disposition: str, key: str) -> str | None:
    marker = f'{key}="'
    if marker not in disposition:
        return None
    value = disposition.split(marker, 1)[1].split('"', 1)[0]
    return unquote(value)


def _safe_filename(filename: str) -> str:
    name = Path(filename).name.replace("\x00", "")
    return "".join(char for char in name if char.isalnum() or char in {" ", ".", "-", "_"}).strip()


def _parse_optional_int(value: str | None) -> int | None:
    if value is None or not value.strip():
        return None
    try:
        parsed = int(value)
    except ValueError:
        return None
    return parsed if parsed > 0 else None


INDEX_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>pdf2epub-recovery</title>
  <link rel="stylesheet" href="/static/app.css">
</head>
<body>
  <main class="shell">
    <section class="intro">
      <div>
        <p class="eyebrow">Local PDF recovery</p>
        <h1>pdf2epub-recovery</h1>
      </div>
      <p class="scope">
        Native-text, mostly one-column PDFs. OCR and complex tables remain unsupported.
      </p>
    </section>

    <section class="workspace">
      <form id="convert-form" class="panel">
        <label class="dropzone" for="pdf">
          <input id="pdf" name="pdf" type="file" accept="application/pdf,.pdf" required>
          <span class="drop-title">PDF auswählen oder hier ablegen</span>
          <span class="drop-help">
            Ziehe eine PDF-Datei in dieses Feld oder klicke zum Auswählen.
          </span>
          <span id="file-name" class="drop-name">Keine Datei ausgewählt</span>
        </label>

        <div class="options">
          <div class="option-row">
            <label><input type="checkbox" name="keep_artifacts"> Seitenreste behalten</label>
            <p>
              Normalerweise entfernt das Tool sichere Seitenzahlen, Kopf- und Fußzeilen.
              Aktiviere dies, wenn nichts entfernt werden soll.
            </p>
          </div>
          <div class="option-row">
            <label>
              <input type="checkbox" name="no_dehyphenate"> Worttrennung nicht reparieren
            </label>
            <p>
              Lässt getrennte Wörter wie im PDF stehen. Nützlich, wenn die automatische
              Reparatur falsche Wörter erzeugt.
            </p>
          </div>
          <div class="option-row">
            <label class="number-field">
              Max Seiten <input type="number" name="max_pages" min="1" step="1">
            </label>
            <p>
              Konvertiert nur die ersten Seiten. Praktisch für einen schnellen Test mit
              großen PDFs.
            </p>
          </div>
        </div>

        <button id="submit" type="submit">EPUB erstellen</button>
      </form>

      <aside class="panel status-panel">
        <div class="status-head">
          <span id="status-label">Idle</span>
          <span id="progress-label">0%</span>
        </div>
        <div class="progress" aria-label="Conversion progress">
          <div id="progress-bar"></div>
        </div>
        <div id="links" class="links"></div>
        <pre id="log" class="log">Waiting for a PDF.</pre>
      </aside>
    </section>
  </main>
  <script src="/static/app.js"></script>
</body>
</html>
"""


STYLE_CSS = """
:root {
  color-scheme: light;
  --bg: #f6f7f9;
  --panel: #ffffff;
  --ink: #17202a;
  --muted: #5f6c7b;
  --line: #d9dee7;
  --accent: #1f7a5c;
  --accent-strong: #155f48;
  --warn: #a15c00;
  --error: #a12727;
}

* {
  box-sizing: border-box;
}

body {
  margin: 0;
  min-height: 100vh;
  background: var(--bg);
  color: var(--ink);
  font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont,
    "Segoe UI", sans-serif;
}

.shell {
  width: min(1080px, calc(100% - 32px));
  margin: 0 auto;
  padding: 40px 0;
}

.intro {
  display: flex;
  align-items: end;
  justify-content: space-between;
  gap: 24px;
  margin-bottom: 24px;
}

.eyebrow {
  margin: 0 0 8px;
  color: var(--accent);
  font-size: 0.82rem;
  font-weight: 700;
  text-transform: uppercase;
}

h1 {
  margin: 0;
  font-size: clamp(2rem, 5vw, 3.5rem);
  line-height: 1;
  letter-spacing: 0;
}

.scope {
  max-width: 420px;
  margin: 0;
  color: var(--muted);
  line-height: 1.5;
}

.workspace {
  display: grid;
  grid-template-columns: minmax(0, 0.95fr) minmax(340px, 1.05fr);
  gap: 20px;
}

.panel {
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 20px;
  box-shadow: 0 12px 30px rgba(23, 32, 42, 0.06);
}

.dropzone {
  display: grid;
  place-items: center;
  align-content: center;
  min-height: 220px;
  border: 2px dashed #9da8b7;
  border-radius: 8px;
  padding: 24px;
  cursor: pointer;
  text-align: center;
  background: #fbfcfd;
  transition: border-color 160ms ease, background 160ms ease;
}

.dropzone.is-dragging {
  border-color: var(--accent);
  background: #edf7f3;
}

.dropzone input {
  position: absolute;
  inline-size: 1px;
  block-size: 1px;
  opacity: 0;
}

.drop-title {
  display: block;
  font-size: 1.3rem;
  font-weight: 700;
}

.drop-help {
  display: block;
  max-width: 28em;
  margin-top: 8px;
  color: var(--muted);
  line-height: 1.45;
}

.drop-name {
  display: block;
  margin-top: 10px;
  color: var(--muted);
  overflow-wrap: anywhere;
}

.options {
  display: grid;
  gap: 16px;
  margin: 20px 0;
}

.option-row {
  display: grid;
  gap: 5px;
}

.option-row p {
  margin: 0 0 0 28px;
  color: var(--muted);
  font-size: 0.92rem;
  line-height: 1.4;
}

.options label {
  display: flex;
  align-items: center;
  gap: 10px;
}

.number-field {
  justify-content: space-between;
}

input[type="number"] {
  width: 92px;
  padding: 8px 10px;
  border: 1px solid var(--line);
  border-radius: 6px;
}

button {
  width: 100%;
  min-height: 46px;
  border: 0;
  border-radius: 7px;
  background: var(--accent);
  color: white;
  font-weight: 700;
  cursor: pointer;
}

button:hover {
  background: var(--accent-strong);
}

button:disabled {
  cursor: progress;
  opacity: 0.65;
}

.status-panel {
  min-height: 360px;
}

.status-head {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 12px;
  font-weight: 700;
}

.progress {
  height: 12px;
  overflow: hidden;
  border-radius: 999px;
  background: #e8edf2;
}

#progress-bar {
  width: 0%;
  height: 100%;
  border-radius: inherit;
  background: var(--accent);
  transition: width 180ms ease;
}

.links {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  min-height: 42px;
  margin: 16px 0;
}

.links a {
  display: inline-flex;
  align-items: center;
  min-height: 34px;
  padding: 0 12px;
  border: 1px solid var(--line);
  border-radius: 6px;
  color: var(--ink);
  text-decoration: none;
}

.log {
  height: 220px;
  margin: 0;
  padding: 14px;
  overflow: auto;
  border: 1px solid var(--line);
  border-radius: 8px;
  background: #111820;
  color: #d8e2ec;
  font: 0.9rem/1.5 ui-monospace, SFMono-Regular, Consolas, "Liberation Mono", monospace;
  white-space: pre-wrap;
}

.status-error {
  color: var(--error);
}

@media (max-width: 820px) {
  .intro,
  .workspace {
    display: grid;
    grid-template-columns: 1fr;
  }

  .shell {
    padding: 24px 0;
  }
}
"""


APP_JS = """
const form = document.querySelector("#convert-form");
const fileInput = document.querySelector("#pdf");
const dropzone = document.querySelector(".dropzone");
const fileName = document.querySelector("#file-name");
const submit = document.querySelector("#submit");
const statusLabel = document.querySelector("#status-label");
const progressLabel = document.querySelector("#progress-label");
const progressBar = document.querySelector("#progress-bar");
const log = document.querySelector("#log");
const links = document.querySelector("#links");

let pollTimer = null;

fileInput.addEventListener("change", () => {
  updateFileName();
});

["dragenter", "dragover"].forEach((eventName) => {
  dropzone.addEventListener(eventName, (event) => {
    event.preventDefault();
    dropzone.classList.add("is-dragging");
  });
});

["dragleave", "drop"].forEach((eventName) => {
  dropzone.addEventListener(eventName, (event) => {
    event.preventDefault();
    dropzone.classList.remove("is-dragging");
  });
});

dropzone.addEventListener("drop", (event) => {
  const file = event.dataTransfer?.files?.[0];
  if (!file) return;
  const transfer = new DataTransfer();
  transfer.items.add(file);
  fileInput.files = transfer.files;
  updateFileName();
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const data = new FormData(form);
  setBusy(true);
  setStatus("Uploading", 0, ["Uploading PDF."]);
  links.innerHTML = "";

  try {
    const response = await fetch("/api/jobs", { method: "POST", body: data });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error || "Upload failed.");
    poll(payload.job_id);
  } catch (error) {
    setBusy(false);
    setStatus("Error", 100, [error.message]);
    statusLabel.classList.add("status-error");
  }
});

async function poll(jobId) {
  clearInterval(pollTimer);
  pollTimer = setInterval(async () => {
    const response = await fetch(`/api/jobs/${jobId}`);
    const payload = await response.json();
    renderJob(payload);
    if (payload.status === "done" || payload.status === "error") {
      clearInterval(pollTimer);
      setBusy(false);
    }
  }, 600);
}

function renderJob(job) {
  statusLabel.classList.toggle("status-error", job.status === "error");
  const statusText = job.status.charAt(0).toUpperCase() + job.status.slice(1);
  setStatus(statusText, job.progress, job.logs || []);
  if (job.status === "done") {
    links.innerHTML = `
      <a href="${job.download_url}">Download EPUB</a>
      <a href="${job.report_url}">Download report</a>
    `;
  }
}

function setStatus(status, progress, lines) {
  statusLabel.textContent = status;
  progressLabel.textContent = `${progress}%`;
  progressBar.style.width = `${progress}%`;
  log.textContent = lines.length ? lines.join("\\n") : "Waiting for a PDF.";
  log.scrollTop = log.scrollHeight;
}

function setBusy(isBusy) {
  submit.disabled = isBusy;
  submit.textContent = isBusy ? "Konvertiere..." : "EPUB erstellen";
}

function updateFileName() {
  fileName.textContent = fileInput.files[0]?.name || "Keine Datei ausgewählt";
}
"""
