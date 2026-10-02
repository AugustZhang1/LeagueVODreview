import os
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

_cache: dict[Path, dict] = {}


def _config_path(path: str | Path | None) -> Path:
    if path is not None:
        return Path(path)
    env = os.environ.get("LOLREVIEW_CONFIG")
    return Path(env) if env else ROOT / "config.toml"


def load_config(path: str | Path | None = None, reload: bool = False) -> dict:
    """Parse config.toml. Cached per path; pass reload=True to read the file again."""
    p = _config_path(path)
    if reload or p not in _cache:
        with open(p, "rb") as f:
            _cache[p] = tomllib.load(f)
    return _cache[p]


def read_env(path: str | Path | None = None) -> dict[str, str]:
    """Parse a .env file (KEY=VALUE lines). Read fresh each call so edits are picked up."""
    p = Path(path) if path is not None else ROOT / ".env"
    out: dict[str, str] = {}
    if not p.exists():
        return out
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.removeprefix("export ").strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        out[key] = value
    return out
