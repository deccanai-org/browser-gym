"""Static file server with SPA fallback — one per mock, inside the task container.

`python -m http.server` is not usable here: the mocks are client-side-routed React
apps, so a request for /item/vm_flipchart_pad or /cart is a 404 on disk and must be
answered with index.html for the router to pick it up. `vite preview` does that
locally; this is the 20-line equivalent with no Node in the image.
"""
from __future__ import annotations

import functools
import http.server
import os
import socketserver
import sys


class SPAHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self) -> None:                                   # noqa: N802
        path = self.translate_path(self.path.split("?", 1)[0])
        if not os.path.exists(path) or os.path.isdir(path):
            # Anything that is not a real file is a client-side route.
            if "." not in os.path.basename(path):
                self.path = "/index.html"
        return super().do_GET()

    def end_headers(self) -> None:
        # The agent's browser loads these from a different origin than the bridge.
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def log_message(self, *a) -> None:                          # keep the job log readable
        pass


def main() -> None:
    root, port = sys.argv[1], int(sys.argv[2])
    handler = functools.partial(SPAHandler, directory=root)
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.ThreadingTCPServer(("127.0.0.1", port), handler) as httpd:
        httpd.serve_forever()


if __name__ == "__main__":
    main()
