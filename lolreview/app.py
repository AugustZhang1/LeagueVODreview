"""The review app: the API plus the built UI on 127.0.0.1.

python -m lolreview.app [--port 8000] [--demo]
"""

import argparse
import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse

from lolreview.api import create_app
from lolreview.config import ROOT

DIST = ROOT / "frontend" / "dist"
HOST = "127.0.0.1"

_MISSING_UI = """<!doctype html>
<meta charset="utf-8"><title>LeagueVODreview</title>
<body style="font-family:sans-serif;max-width:40em;margin:3em auto">
<h1>The UI isn't built yet</h1>
<p>Build it once, then reload:</p>
<pre>cd frontend &amp;&amp; npm ci &amp;&amp; npm run build</pre>
<p>The API is already running under <code>/api</code>.</p>
</body>"""


def build_app(demo: bool | None = None, dist: Path = DIST, **kwargs) -> FastAPI:
    """The API app with the built UI mounted behind it."""
    app = create_app(demo=demo, **kwargs)
    dist = Path(dist).resolve()

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        if path == "api" or path.startswith("api/"):
            return JSONResponse(
                status_code=404,
                content={"error": {"code": "not_found", "message": "Not found."}},
            )
        index = dist / "index.html"
        if not index.is_file():
            return HTMLResponse(_MISSING_UI, status_code=200 if path == "" else 404)
        target = (dist / path).resolve()
        if path and target.is_file() and target.is_relative_to(dist):
            return FileResponse(target)
        return FileResponse(index)

    return app


def main(argv: list[str] | None = None) -> None:
    import uvicorn

    parser = argparse.ArgumentParser(description="Run the review app.")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--demo", action="store_true", help="synthetic games, no Riot key")
    args = parser.parse_args(argv)
    demo = args.demo or os.environ.get("LOLREVIEW_DEMO") == "1"
    app = build_app(demo=demo)
    print(f"LeagueVODreview{' (demo)' if demo else ''}: http://{HOST}:{args.port}", flush=True)
    uvicorn.run(app, host=HOST, port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
