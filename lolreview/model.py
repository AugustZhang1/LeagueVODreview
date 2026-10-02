"""Win-probability model: the trained LightGBM booster, or a hand-set placeholder."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import numpy as np

from lolreview.features import FEATURE_COLUMNS, SOUL_TYPES

MODEL_FILES = ("model.txt", "isotonic.json", "metrics.json")


class FeatureMismatch(ValueError):
    """The model file was trained on a different feature list than features.py has."""


def _signature(models_dir: Path) -> tuple:
    out = []
    for name in MODEL_FILES:
        try:
            out.append((name, (models_dir / name).stat().st_mtime_ns))
        except OSError:
            out.append((name, None))
    return tuple(out)


class WinModel:
    kind = "stub"
    version = "stub"
    trained_at: str | None = None
    patches: list[str] | None = None
    metrics: dict | None = None
    signature: tuple = ()

    def predict(self, rows: list[dict]) -> list[float]:
        """Blue win probability for each feature row."""
        raise NotImplementedError


class PlaceholderModel(WinModel):
    """Logistic formula with hand-set weights, so the app runs before a model is trained."""

    kind = "stub"
    version = "stub"
    # Log-odds per unit of each blue-minus-red feature. The first group is scaled by a time
    # factor (the same lead means more late); objectives count the same all game.
    SCALED_WEIGHTS = {
        "gold_diff": 0.0001,
        "kill_diff": 0.045,
        "level_diff": 0.03,
        "cs_diff": 0.002,
    }
    WEIGHTS = {
        "tower_diff": 0.16,
        "inhibs_down_diff": 0.7,
        "baron_active": 0.9,
        "elder_active": 0.9,
        "soul_diff": 0.4,
        "grub_diff": 0.08,
        "herald_diff": 0.15,
        "quest_diff": 0.06,
        "blue_dragons": 0.15,
        "red_dragons": -0.15,
    }

    def __init__(self, signature: tuple = ()) -> None:
        self.signature = signature

    @staticmethod
    def time_factor(minute: float) -> float:
        return 0.6 + 1.4 * min(max(minute, 0.0), 40.0) / 40.0

    def predict(self, rows: list[dict]) -> list[float]:
        out = []
        for row in rows:
            factor = self.time_factor(float(row.get("minute", 0)))
            z = sum(w * float(row.get(name, 0)) for name, w in self.WEIGHTS.items())
            z += factor * sum(w * float(row.get(n, 0)) for n, w in self.SCALED_WEIGHTS.items())
            out.append(1.0 / (1.0 + math.exp(-z)))
        return out


class TrainedModel(WinModel):
    kind = "trained"

    def __init__(self, models_dir: Path) -> None:
        import lightgbm as lgb

        path = models_dir / "model.txt"
        self.booster = lgb.Booster(model_file=str(path))
        names = list(self.booster.feature_name())
        if names != FEATURE_COLUMNS:
            raise FeatureMismatch(
                f"{path} was trained on features {names}, but features.py has {FEATURE_COLUMNS}; "
                "retrain the model or restore the matching features.py"
            )
        self.signature = _signature(models_dir)
        metrics = models_dir / "metrics.json"
        if metrics.exists():
            self.metrics = json.loads(metrics.read_text(encoding="utf-8"))
            self.trained_at = self.metrics.get("trained_at")
            self.patches = self.metrics.get("patches")
        calibrated = self.metrics.get("isotonic", True) if metrics.exists() else True
        digest = hashlib.sha256(path.read_bytes())
        self.iso: tuple[np.ndarray, np.ndarray] | None = None
        iso = models_dir / "isotonic.json"
        if calibrated and iso.exists():
            raw = iso.read_bytes()
            digest.update(raw)
            d = json.loads(raw)
            self.iso = (np.asarray(d["x"], dtype=float), np.asarray(d["y"], dtype=float))
        self.version = digest.hexdigest()[:8]

    @staticmethod
    def _encode(row: dict) -> list[float]:
        out = []
        for col in FEATURE_COLUMNS:
            v = row[col]
            if col == "soul_type":
                v = SOUL_TYPES.index(v) if v in SOUL_TYPES else -1
            out.append(float(v))
        return out

    def predict(self, rows: list[dict]) -> list[float]:
        if not rows:
            return []
        x = np.array([self._encode(r) for r in rows], dtype=float)
        p = self.booster.predict(x)
        if self.iso is not None:
            p = np.interp(p, self.iso[0], self.iso[1])
        return [float(v) for v in p]


def load_model(models_dir: str | Path) -> WinModel:
    d = Path(models_dir)
    if (d / "model.txt").exists():
        return TrainedModel(d)
    return PlaceholderModel(_signature(d))


def models_changed(models_dir: str | Path, current: WinModel) -> bool:
    """True when the model files on disk differ from the ones `current` was loaded from."""
    return _signature(Path(models_dir)) != current.signature
