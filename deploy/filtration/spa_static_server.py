#!/usr/bin/env python3
"""Minimal SPA static server for baked hub mock dist (index.html fallback)."""
from __future__ import annotations

import argparse
import mimetypes
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse


def make_handler(root: Path):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *args) -> None:  # quieter on Cloud Run
            if os.environ.get("SPA_SERVER_VERBOSE"):
                super().log_message(fmt, *args)

        def do_GET(self) -> None:  # noqa: N802
            path = unquote(urlparse(self.path).path)
            if path.endswith("/"):
                path = path + "index.html"
            rel = path.lstrip("/")
            candidate = (root / rel).resolve()
            try:
                candidate.relative_to(root.resolve())
            except ValueError:
                self.send_error(403)
                return
            if candidate.is_file():
                self._send_file(candidate)
                return
            # SPA fallback
            index = root / "index.html"
            if index.is_file():
                self._send_file(index)
                return
            self.send_error(404)

        def _send_file(self, path: Path) -> None:
            data = path.read_bytes()
            ctype, _ = mimetypes.guess_type(str(path))
            self.send_response(200)
            self.send_header("Content-Type", ctype or "application/octet-stream")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(data)

    return Handler


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True)
    ap.add_argument("--port", type=int, required=True)
    ap.add_argument("--bind", default="127.0.0.1")
    args = ap.parse_args()
    root = Path(args.root).resolve()
    if not root.is_dir():
        raise SystemExit(f"root not a directory: {root}")
    httpd = ThreadingHTTPServer((args.bind, args.port), make_handler(root))
    httpd.serve_forever()


if __name__ == "__main__":
    main()
