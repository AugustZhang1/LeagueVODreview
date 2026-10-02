"""Progress page for the crawler (Plan.md Step 6): stdlib http.server, no JavaScript."""

import json
import threading
import time
from collections.abc import Callable
from datetime import UTC, datetime
from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from lolreview.config import load_config
from lolreview.state import State, state_path

KEY_UPDATE_COMMAND = (
    "gcloud compute ssh lol-crawler -- "
    "\"sed -i 's/^RIOT_API_KEY=.*/RIOT_API_KEY=NEW_KEY/' ~/LeagueVODreview/.env\""
)
REFRESH_S = 300

CSS = """
:root{--bg:#0e1217;--surface:#151a21;--surface-2:#1a1f27;--border:#2a313b;--text:#e8e6e1;
--text-2:#a3a7ad;--text-3:#858a92;--ally:#3987e5;--enemy:#e66767;--you:#d4b26a}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--text);font:14px/1.5 system-ui,sans-serif}
main{max-width:960px;margin:0 auto;padding:24px 16px}
h1{font-size:20px;font-weight:600;margin:0 0 4px}
h2{font-size:16px;font-weight:600;margin:0 0 12px}
.sub,.muted{color:var(--text-3);font-size:12px}
section{background:var(--surface);border:1px solid var(--border);border-radius:8px;
padding:16px;margin-top:32px}
.banner{border-left:3px solid var(--enemy);background:var(--surface);padding:12px 16px;
margin-top:24px;border-radius:0 8px 8px 0}
.banner b{color:var(--enemy)}
code{font:12px ui-monospace,monospace;color:var(--text-2);word-break:break-all}
table{border-collapse:collapse;width:100%;font-variant-numeric:tabular-nums}
th,td{text-align:left;padding:6px 8px;border-bottom:1px solid var(--border)}
th{color:var(--text-2);font-weight:500}
tr:last-child td{border-bottom:0}
td.n,th.n{text-align:right}
.bar{background:var(--surface-2);border-radius:6px;height:8px;width:100%;min-width:120px}
.bar i{display:block;background:var(--ally);height:8px;border-radius:6px}
.stats{display:flex;flex-wrap:wrap;gap:8px 32px}
.stats div span{display:block}
.err{color:var(--enemy)}
"""

_SEVERITY = {"ok": 0, "missing": 1, "expired": 2}


def _clock(ts: float) -> str:
    return datetime.fromtimestamp(ts, UTC).strftime("%H:%M")


def _age(seconds: float) -> str:
    seconds = max(0, int(seconds))
    if seconds < 90:
        return f"{seconds} s ago"
    if seconds < 5400:
        return f"{round(seconds / 60)} min ago"
    if seconds < 172800:
        return f"{seconds / 3600:.1f} h ago"
    return f"{seconds // 86400} days ago"


def _size(n: float) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} GB"


def _length(seconds: float) -> str:
    return f"{int(seconds // 60)}:{int(seconds % 60):02d}"


def _title(tier: str, division: str = "") -> str:
    name = tier.capitalize()
    return (
        f"{name} {division}"
        if division and tier not in ("CHALLENGER", "GRANDMASTER", "MASTER")
        else name
    )


def build_snapshot(
    data_dir: Path,
    platforms: list[str],
    key_status: Callable[[], dict[str, str]] | None = None,
    cfg: dict | None = None,
    now: float | None = None,
) -> dict:
    """Collect everything the page shows from the per-platform state files."""
    cfg = cfg if cfg is not None else load_config()
    crawl = cfg["crawl"]
    now = time.time() if now is None else now
    cap = int(crawl["games_per_tier_per_pass"])
    tiers = list(crawl["tiers"])
    tiers = tiers[: tiers.index(crawl["bottom_tier"].upper()) + 1]
    keys = key_status() if key_status else {}

    clusters = []
    tier_fraction = {t: [] for t in tiers}
    totals = {"games": 0, "rows": 0, "bytes": 0, "blue_wins": 0, "duration_s": 0}
    patch_games: dict[str, int] = {}
    counts = {"requests": 0, "http_429": 0, "http_5xx": 0}
    errors: list[tuple[float, str]] = []
    last_batch = None
    for platform in platforms:
        path = state_path(data_dir, platform)
        if not path.exists():
            continue
        st = State(path)
        try:
            tot = st.totals()
            for k in totals:
                totals[k] += tot[k]
            if tot["last_batch"] is not None:
                last_batch = max(last_batch or 0, tot["last_batch"])
            for patch, n in st.patch_games().items():
                patch_games[patch] = patch_games.get(patch, 0) + n
            for k, v in st.counts_since(int(now // 60) - 60).items():
                counts[k] += v
            errors += st.recent_errors(10)
            started = float(st.meta_get("started_at", now))
            hours = max(min(3600.0, now - started), 60.0) / 3600
            tier = st.meta_get("tier", tiers[0])
            pass_no = st.meta_int("pass_no", 1)
            cur = st.meta_int("tier_idx", 0)
            for i, t in enumerate(tiers):
                if i < cur:
                    frac = 1.0
                else:
                    frac = min(st.meta_int(f"added:{pass_no}:{t}", 0) / cap, 1.0)
                tier_fraction[t].append(frac)
            clusters.append(
                {
                    "platform": platform,
                    "tier": tier,
                    "division": st.meta_get("division", ""),
                    "pass_no": pass_no,
                    "games": tot["games"],
                    "per_hour": st.games_since(now - 3600) / hours,
                    "pending": st.match_counts().get("pending", 0),
                    "key": keys.get(platform, "ok"),
                }
            )
        finally:
            st.close()

    games = totals["games"]
    upload = None
    upload_path = Path(data_dir) / "last_upload.json"
    try:
        upload = json.loads(upload_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        pass
    key = max((c["key"] for c in clusters), key=lambda k: _SEVERITY.get(k, 0), default="ok")
    errors.sort(reverse=True)
    return {
        "now": now,
        "key": key,
        "clusters": clusters,
        "tiers": [
            {"tier": t, "pct": 100 * sum(f) / len(f) if f else 0.0}
            for t, f in tier_fraction.items()
        ],
        "last_hour": counts,
        "last_batch": last_batch,
        "data": {
            "games": games,
            "rows": totals["rows"],
            "bytes": totals["bytes"],
            "blue_win_rate": totals["blue_wins"] / games if games else None,
            "avg_length_s": totals["duration_s"] / games if games else None,
            "patches": [(p, n, n / games) for p, n in sorted(patch_games.items(), reverse=True)],
        },
        "upload": upload,
        "errors": errors[:10],
    }


def _stat(label: str, value: str) -> str:
    return f'<div><span class="muted">{label}</span><span>{value}</span></div>'


def _table(head: list[str], rows: list[list[str]], numeric: set[int] = frozenset()) -> str:
    def cell(tag: str, i: int, text: str) -> str:
        cls = ' class="n"' if i in numeric else ""
        return f"<{tag}{cls}>{text}</{tag}>"

    out = ["<table>"]
    if head:
        out.append("<tr>" + "".join(cell("th", i, h) for i, h in enumerate(head)) + "</tr>")
    for row in rows:
        out.append("<tr>" + "".join(cell("td", i, c) for i, c in enumerate(row)) + "</tr>")
    out.append("</table>")
    return "".join(out)


def render(snapshot: dict) -> str:
    now = snapshot["now"]
    key = snapshot["key"]
    parts = []
    if key == "expired":
        parts.append(
            '<div class="banner"><b>Key expired</b> Riot rejected the API key. The crawler is '
            "waiting and picks up a new key within a minute. Update it from the laptop:<br>"
            f"<code>{escape(KEY_UPDATE_COMMAND)}</code></div>"
        )
    elif key == "missing":
        parts.append(
            '<div class="banner"><b>Key missing</b> RIOT_API_KEY is not set in .env. '
            f"Add it with:<br><code>{escape(KEY_UPDATE_COMMAND)}</code></div>"
        )

    last = snapshot["last_batch"]
    hour = snapshot["last_hour"]
    key_label = "OK" if key == "ok" else key.upper()
    parts.append(
        '<section><h2>Health</h2><div class="stats">'
        + _stat("Key", escape(key_label))
        + _stat("429s, last hour", f"{hour['http_429']:,}")
        + _stat("5xx, last hour", f"{hour['http_5xx']:,}")
        + _stat("Requests, last hour", f"{hour['requests']:,}")
        + _stat("Last batch", _age(now - last) if last else "none yet")
        + "</div></section>"
    )

    rows = [
        [
            escape(c["platform"].upper()),
            escape(_title(c["tier"], c["division"])),
            f"{c['games']:,}",
            f"{c['per_hour']:,.0f}/h",
            f"{c['pending']:,}",
            f"{c['pass_no']}",
        ]
        for c in snapshot["clusters"]
    ]
    parts.append(
        "<section><h2>Per cluster</h2>"
        + _table(
            ["Cluster", "Now crawling", "Games", "Games per hour", "Pending", "Pass"],
            rows,
            {2, 3, 4, 5},
        )
        + "</section>"
    )

    rows = []
    for t in snapshot["tiers"]:
        pct = t["pct"]
        label = "done" if pct >= 99.95 else f"{pct:.0f}%"
        bar = f'<div class="bar"><i style="width:{min(pct, 100):.1f}%"></i></div>'
        rows.append([escape(_title(t["tier"])), bar, label])
    parts.append("<section><h2>By tier</h2>" + _table([], rows, {2}) + "</section>")

    d = snapshot["data"]
    blue = f"{d['blue_win_rate'] * 100:.1f}%" if d["blue_win_rate"] is not None else "n/a"
    length = _length(d["avg_length_s"]) if d["avg_length_s"] is not None else "n/a"
    mix = ", ".join(f"{escape(p)} ({share * 100:.0f}%)" for p, _, share in d["patches"]) or "none"
    parts.append(
        '<section><h2>Data</h2><div class="stats">'
        f'<div><span class="muted">Patches kept</span><span>{mix}</span></div>'
        f'<div><span class="muted">Games</span><span>{d["games"]:,}</span></div>'
        f'<div><span class="muted">Rows</span><span>{d["rows"]:,}</span></div>'
        f'<div><span class="muted">Disk used</span><span>{_size(d["bytes"])}</span></div>'
        f'<div><span class="muted">Blue win rate</span><span>{blue}</span></div>'
        f'<div><span class="muted">Average length</span><span>{length}</span></div>'
        "</div></section>"
    )

    up = snapshot["upload"]
    if up:
        try:
            when = _age(now - datetime.fromisoformat(up["uploaded_at"]).timestamp())
        except (KeyError, ValueError):
            when = "at an unknown time"
        text = f"Last upload: {int(up.get('games', 0)):,} games, {when}"
    else:
        text = "No upload yet"
    parts.append(f"<section><h2>Kaggle</h2><div>{escape(text)}</div></section>")

    errs = [[_clock(at), escape(msg)] for at, msg in snapshot["errors"]]
    body = _table([], errs) if errs else '<div class="muted">None</div>'
    parts.append(f"<section><h2>Recent errors</h2>{body}</section>")

    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f'<meta http-equiv="refresh" content="{REFRESH_S}">'
        f"<title>Crawl progress</title><style>{CSS}</style></head><body><main>"
        f'<h1>Crawl progress</h1><div class="sub">Updated {_clock(now)} UTC</div>'
        + "".join(parts)
        + "</main></body></html>"
    )


def serve(
    data_dir: Path,
    platforms: list[str],
    port: int,
    key_status: Callable[[], dict[str, str]] | None = None,
    cfg: dict | None = None,
) -> ThreadingHTTPServer:
    """Start the page on 127.0.0.1:<port> in a daemon thread; port 0 picks a free one."""

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            path = self.path.split("?", 1)[0]
            if path == "/healthz":
                body, kind, code = b"ok", "text/plain; charset=utf-8", 200
            elif path == "/":
                try:
                    html = render(build_snapshot(data_dir, platforms, key_status, cfg))
                    body, kind, code = html.encode("utf-8"), "text/html; charset=utf-8", 200
                except Exception as e:
                    body, kind, code = f"error: {e}".encode(), "text/plain; charset=utf-8", 500
            else:
                body, kind, code = b"not found", "text/plain; charset=utf-8", 404
            self.send_response(code)
            self.send_header("Content-Type", kind)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    server.daemon_threads = True
    threading.Thread(target=server.serve_forever, name="status", daemon=True).start()
    return server
