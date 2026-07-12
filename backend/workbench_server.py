#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
from datetime import UTC, datetime
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from category_workbench import (
    ROOT,
    add_candidate,
    category_state,
    price_refresh_status,
    remove_holding,
    search_category,
    set_start_date,
    validate_taxonomy,
)
from ticker_intake import (
    add_approved_tickers,
    classify_intake,
    context_intake,
    openai_status,
    parse_intake,
)
from portfolio_review.workflow import (
    OUTPUT_DIR as PORTFOLIO_REVIEW_DIR,
    load_current_review,
    run_portfolio_review_api,
)
from portfolio_review.importer import import_portfolio_csv_api
from market_config import sync_config_end_date


RUN_LOCK = threading.Lock()
PROJECT_ROOT = ROOT.parent
WORKSTATION_HTML = ROOT / "market-basket-analyst-workstation.html"
WORKSTATION_CSS = PROJECT_ROOT / "public" / "workstation-enhancements.css"
WORKSTATION_JS = PROJECT_ROOT / "public" / "workstation-enhancements.js"
WORKSTATION_ICON = PROJECT_ROOT / "public" / "favicon.svg"
RUN_STATUS: dict = {
    "running": False,
    "state": "idle",
    "startedAt": "",
    "finishedAt": "",
    "runId": "",
    "returnCode": None,
    "command": [],
    "autoRefreshReasons": [],
    "log": [],
    "error": "",
}

OPENAI_RUNTIME: dict[str, str] = {
    "api_key": "",
    "model": "",
}


def read_json_file(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text())


def append_log(line: str) -> None:
    with RUN_LOCK:
        RUN_STATUS["log"].append(line.rstrip())
        RUN_STATUS["log"] = RUN_STATUS["log"][-300:]


def set_run_status(**updates: object) -> None:
    with RUN_LOCK:
        RUN_STATUS.update(updates)


def snapshot_run_status() -> dict:
    with RUN_LOCK:
        return json.loads(json.dumps(RUN_STATUS))


def run_pipeline_background(options: dict) -> None:
    run_id = datetime.now(UTC).strftime("workbench_%Y%m%dT%H%M%SZ")
    command = [sys.executable, "run_pipeline.py", "--run-id", run_id]
    try:
        sync_result = sync_config_end_date()
    except Exception as exc:  # pragma: no cover - surfaced in API status
        set_run_status(
            running=False,
            state="failed",
            startedAt=datetime.now(UTC).isoformat(timespec="seconds"),
            finishedAt=datetime.now(UTC).isoformat(timespec="seconds"),
            runId=run_id,
            returnCode=1,
            command=command,
            autoRefreshReasons=[],
            log=[f"ERROR: could not update analysis end date: {exc}"],
            error=str(exc),
        )
        return
    price_status = price_refresh_status()
    auto_refresh_reasons = []
    if sync_result["dateChanged"]:
        auto_refresh_reasons.append(
            f"Analysis end date updated from {sync_result['previousEndDate']} to {sync_result['endDate']}."
        )
    refresh_prices = bool(options.get("refreshPrices") or price_status["required"])
    if refresh_prices:
        command.append("--refresh-prices")
    if options.get("refreshFundamentals"):
        command.append("--refresh-fundamentals")
    if options.get("refreshPositioning"):
        command.append("--refresh-positioning")
    if options.get("refreshOwnership"):
        command.append("--refresh-ownership")

    set_run_status(
        running=True,
        state="running",
        startedAt=datetime.now(UTC).isoformat(timespec="seconds"),
        finishedAt="",
        runId=run_id,
        returnCode=None,
        command=command,
        autoRefreshReasons=auto_refresh_reasons
        + (price_status["reasons"] if price_status["required"] and not options.get("refreshPrices") else []),
        log=[],
        error="",
    )
    append_log("$ " + " ".join(command))
    if price_status["required"] and not options.get("refreshPrices"):
        append_log("Auto-enabled fresh prices:")
        for reason in price_status["reasons"]:
            append_log(f"- {reason}")
    try:
        process = subprocess.Popen(
            command,
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        assert process.stdout is not None
        for line in process.stdout:
            append_log(line)
        return_code = process.wait()
        set_run_status(
            running=False,
            state="complete" if return_code == 0 else "failed",
            finishedAt=datetime.now(UTC).isoformat(timespec="seconds"),
            returnCode=return_code,
        )
    except Exception as exc:  # pragma: no cover - surfaced in API status
        set_run_status(
            running=False,
            state="failed",
            finishedAt=datetime.now(UTC).isoformat(timespec="seconds"),
            returnCode=1,
            error=str(exc),
        )
        append_log(f"ERROR: {exc}")


class WorkbenchHandler(SimpleHTTPRequestHandler):
    server_version = "MarketWorkbench/1.0"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def log_message(self, format: str, *args) -> None:
        sys.stderr.write("[%s] %s\n" % (self.log_date_time_string(), format % args))

    def send_json(self, payload: object, status: HTTPStatus = HTTPStatus.OK) -> None:
        encoded = json.dumps(payload, indent=2).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(encoded)

    def send_asset(self, content: bytes, content_type: str) -> None:
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store, max-age=0")
        self.end_headers()
        self.wfile.write(content)

    def end_headers(self) -> None:
        path = urlparse(self.path).path
        if (
            path == "/"
            or path.endswith(".html")
            or path.startswith("/data/")
            or path.startswith("/config/")
        ):
            self.send_header("Cache-Control", "no-store, max-age=0")
            self.send_header("Pragma", "no-cache")
            self.send_header("Expires", "0")
        super().end_headers()

    def read_body(self) -> dict:
        length = int(self.headers.get("Content-Length", "0") or 0)
        if not length:
            return {}
        return json.loads(self.rfile.read(length).decode())

    def api_state(self) -> dict:
        return {
            **category_state(),
            "qa": read_json_file(ROOT / "data" / "qa_report.json"),
            "run": snapshot_run_status(),
            "openai": openai_status(OPENAI_RUNTIME["api_key"], OPENAI_RUNTIME["model"]),
        }

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        if path in {"/", "/workstation"}:
            html = WORKSTATION_HTML.read_text()
            enhanced = html.replace(
                "</head>",
                '<link rel="stylesheet" href="/workstation-enhancements.css?v=2">'
                '<link rel="icon" href="/favicon.svg" type="image/svg+xml">'
                '<script defer src="/workstation-enhancements.js?v=1"></script>'
                '<meta name="theme-color" content="#080b11"></head>',
            )
            self.send_asset(enhanced.encode(), "text/html; charset=utf-8")
            return
        if path == "/workstation-enhancements.css":
            self.send_asset(WORKSTATION_CSS.read_bytes(), "text/css; charset=utf-8")
            return
        if path == "/workstation-enhancements.js":
            self.send_asset(WORKSTATION_JS.read_bytes(), "text/javascript; charset=utf-8")
            return
        if path == "/favicon.svg":
            self.send_asset(WORKSTATION_ICON.read_bytes(), "image/svg+xml")
            return
        if path == "/api/state":
            self.send_json(self.api_state())
            return
        if path == "/api/run/status":
            self.send_json(snapshot_run_status())
            return
        if path == "/api/portfolio-review/current":
            self.send_json(load_current_review(PORTFOLIO_REVIEW_DIR))
            return
        if path == "/api/categories":
            self.send_json(category_state())
            return
        if path == "/api/openai/status":
            self.send_json(openai_status(OPENAI_RUNTIME["api_key"], OPENAI_RUNTIME["model"]))
            return
        if path.startswith("/api/categories/") and path.endswith("/search"):
            parts = path.strip("/").split("/")
            if len(parts) != 4:
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            category_id = unquote(parts[2])
            query = parse_qs(parsed.query).get("q", [""])[0]
            try:
                self.send_json({"results": search_category(category_id, query)})
            except KeyError as exc:
                self.send_json({"error": str(exc)}, HTTPStatus.NOT_FOUND)
            return
        super().do_GET()

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        try:
            body = self.read_body()
            if path == "/api/config/start-date":
                self.send_json(set_start_date(str(body.get("startDate", ""))))
                return
            if path.startswith("/api/categories/") and path.endswith("/add"):
                parts = path.strip("/").split("/")
                self.send_json(add_candidate(unquote(parts[2]), str(body.get("ticker", ""))))
                return
            if path.startswith("/api/categories/") and path.endswith("/remove"):
                parts = path.strip("/").split("/")
                self.send_json(remove_holding(unquote(parts[2]), str(body.get("ticker", ""))))
                return
            if path == "/api/openai/key":
                api_key = str(body.get("apiKey", "")).strip()
                model = str(body.get("model", "")).strip()
                if body.get("forget"):
                    OPENAI_RUNTIME["api_key"] = ""
                elif api_key:
                    OPENAI_RUNTIME["api_key"] = api_key
                if model:
                    OPENAI_RUNTIME["model"] = model
                self.send_json(openai_status(OPENAI_RUNTIME["api_key"], OPENAI_RUNTIME["model"]))
                return
            if path == "/api/ticker-intake/parse":
                self.send_json(parse_intake(str(body.get("text", ""))))
                return
            if path == "/api/ticker-intake/context":
                self.send_json(
                    context_intake(
                        str(body.get("text", "")),
                        refresh=bool(body.get("refresh")),
                        workers=int(body.get("workers") or 8),
                    )
                )
                return
            if path == "/api/ticker-intake/classify":
                api_key = OPENAI_RUNTIME["api_key"] or os.environ.get("OPENAI_API_KEY", "").strip()
                model = str(body.get("model") or OPENAI_RUNTIME["model"] or "").strip()
                self.send_json(
                    classify_intake(
                        str(body.get("text", "")),
                        api_key,
                        model=model,
                        context_workers=int(body.get("contextWorkers") or 8),
                        llm_workers=int(body.get("llmWorkers") or 4),
                        chunk_size=int(body.get("chunkSize") or 5),
                        refresh_context=bool(body.get("refreshContext")),
                    )
                )
                return
            if path == "/api/ticker-intake/add":
                rows = body.get("rows", [])
                if not isinstance(rows, list):
                    raise ValueError("rows must be a list")
                self.send_json(add_approved_tickers(rows))
                return
            if path == "/api/run":
                with RUN_LOCK:
                    if RUN_STATUS["running"]:
                        self.send_json({"error": "A pipeline run is already in progress", "run": snapshot_run_status()}, HTTPStatus.CONFLICT)
                        return
                thread = threading.Thread(target=run_pipeline_background, args=(body,), daemon=True)
                thread.start()
                time.sleep(0.05)
                self.send_json(snapshot_run_status(), HTTPStatus.ACCEPTED)
                return
            if path == "/api/portfolio-review/run":
                self.send_json(run_portfolio_review_api(body))
                return
            if path == "/api/portfolio-review/import-csv":
                self.send_json(import_portfolio_csv_api(body, ROOT / "data"))
                return
            self.send_error(HTTPStatus.NOT_FOUND)
        except ValueError as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
        except KeyError as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.NOT_FOUND)
        except json.JSONDecodeError as exc:
            self.send_json({"error": f"Invalid JSON: {exc}"}, HTTPStatus.BAD_REQUEST)


def main() -> int:
    problems = validate_taxonomy()
    if problems:
        print("Category taxonomy validation failed:")
        for problem in problems:
            print(f"- {problem}")
        return 1
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 3000
    server = ThreadingHTTPServer(("127.0.0.1", port), WorkbenchHandler)
    print(f"Workbench server: http://127.0.0.1:{port}/workstation")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping workbench server")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
