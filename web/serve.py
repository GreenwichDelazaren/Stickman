"""Serve web/dist on http://localhost:8000 to try the website (build it first: python web/build.py).

    python web/serve.py [port]

Like python -m http.server, but with the right content types: on Windows that one can serve .js as
text/plain (from the registry), which browsers refuse to run as a module.
"""

import functools
import http.server
import os
import sys

DIST = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dist")
TYPES = {".js": "text/javascript", ".mjs": "text/javascript", ".css": "text/css", ".html": "text/html",
         ".json": "application/json", ".png": "image/png", ".py": "text/plain; charset=utf-8",
         ".wasm": "application/wasm"}


class Handler(http.server.SimpleHTTPRequestHandler):
    extensions_map = {**http.server.SimpleHTTPRequestHandler.extensions_map, **TYPES}


def serve(port=8000):
    if not os.path.isdir(DIST):
        sys.exit("web/dist doesn't exist yet: run python web/build.py first")
    server = http.server.ThreadingHTTPServer(("127.0.0.1", port), functools.partial(Handler, directory=DIST))
    print(f"Serving {DIST} on http://localhost:{port} (Ctrl+C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    serve(int(sys.argv[1]) if len(sys.argv) > 1 else 8000)
