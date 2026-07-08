#!/usr/bin/env python3
"""Read-only local static server for the frontend report viewer."""

from __future__ import annotations

import http.server
import os
import socketserver


PORT = 8000
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format, *args):
        pass


class ReusableTCPServer(socketserver.TCPServer):
    allow_reuse_address = True


def main() -> None:
    os.chdir(ROOT)
    with ReusableTCPServer(("", PORT), QuietHandler) as httpd:
        print(f"Local viewer server: http://127.0.0.1:{PORT}/frontend/")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nServer stopped.")


if __name__ == "__main__":
    main()
