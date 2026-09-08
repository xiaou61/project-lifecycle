"""Serve a VitePress build with clean-URL fallbacks using the standard library."""

from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import os
import sys


class CleanURLHandler(SimpleHTTPRequestHandler):
    def translate_path(self, path: str) -> str:
        translated = super().translate_path(path)
        if Path(translated).is_file():
            return translated
        if path.endswith("/"):
            candidate = Path(translated) / "index.html"
        else:
            candidate = Path(f"{translated}.html")
        return str(candidate) if candidate.is_file() else translated


def main() -> None:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    port = int(sys.argv[2] if len(sys.argv) > 2 else "4175")
    os.chdir(root)
    server = ThreadingHTTPServer(("0.0.0.0", port), CleanURLHandler)
    print(f"Serving {root} on http://0.0.0.0:{port}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
