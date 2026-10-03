"""Win-probability model: the trained LightGBM booster, or a hand-set placeholder."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import numpy as np

from lolreview.constants import PRO_TIER_INDEX, TIER_INDEX
from lolreview.features import (
    CHAMPION_FEATURES,
    FEATURE_COLUMNS,
    SOUL_TYPES,
    champion_features,
)

MODEL_FILES = ("model.txt", "isotonic.json", "metrics.json", "champions.json")


class FeatureMismatch(ValueError):
    """The model file was trained on a different feature list than features.py has."""


def _signature(models_dir: Path) -> tuple:
    out = []
    for name in MODEL_FILES:
        try:
            out.append((name, (models_dir / name).stat().st_mtime_ns))
        except OSError:
            out.append((name, None))
    for f in sorted((models_dir / "tiers").glob("*/*")):  # rank models
        out.append((f.relative_to(models_dir).as_posix(), f.stat().st_mtime_ns))
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
        "alive_diff": 0.05,
        "blue_dead_s": -0.001,
        "red_dead_s": 0.001,
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

    def __init__(self, models_dir: Path, champions: dict | None = None) -> None:
        import lightgbm as lgb

        path = models_dir / "model.txt"
        self.booster = lgb.Booster(model_file=str(path))
        # An older features version's model keeps working: it reads only the columns it knows
        self.columns = list(self.booster.feature_name())
        unknown = [c for c in self.columns if c not in FEATURE_COLUMNS + CHAMPION_FEATURES]
        if unknown:
            raise FeatureMismatch(
                f"{path} was trained on features {self.columns}, but features.py has no "
                f"{unknown}; retrain the model or restore the matching features.py"
            )
        self.signature = _signature(models_dir)
        metrics = models_dir / "metrics.json"
        if metrics.exists():
            self.metrics = json.loads(metrics.read_text(encoding="utf-8"))
            self.trained_at = self.metrics.get("trained_at")
            self.patches = self.metrics.get("patches")
        calibrated = self.metrics.get("isotonic", True) if metrics.exists() else True
        digest = hashlib.sha256(path.read_bytes())
        # Per-champion table for the champion columns; rank models use their parent's
        table = models_dir / "champions.json"
        if champions is None and table.exists():
            raw = table.read_bytes()
            digest.update(raw)
            champions = json.loads(raw)
        self.champions: dict = champions or {}
        self.uses_champions = any(c in CHAMPION_FEATURES for c in self.columns)
        if self.uses_champions and not self.champions:
            raise FeatureMismatch(f"{path} uses champion columns but champions.json is missing")
        self.iso: tuple[np.ndarray, np.ndarray] | None = None
        iso = models_dir / "isotonic.json"
        if calibrated and iso.exists():
            raw = iso.read_bytes()
            digest.update(raw)
            d = json.loads(raw)
            self.iso = (np.asarray(d["x"], dtype=float), np.asarray(d["y"], dtype=float))
        # Rank models from train.py, each saved only where it beat this one on that rank's games
        self.by_tier: dict[int, TrainedModel] = {}
        for f in sorted((models_dir / "tiers").glob("*/model.txt")):
            name = f.parent.name
            index = PRO_TIER_INDEX if name == "PRO" else TIER_INDEX.get(name)
            if index is not None:
                self.by_tier[index] = TrainedModel(f.parent, self.champions)
                digest.update(f"{name}:{self.by_tier[index].version}".encode())
        self.version = digest.hexdigest()[:8]

    def _encode(self, row: dict) -> list[float]:
        if self.uses_champions:
            row = {**row, **champion_features(row["blue_champs"], row["red_champs"],
                                              self.champions)}  # fmt: skip
        out = []
        for col in self.columns:
            v = row[col]
            if col == "soul_type":
                v = SOUL_TYPES.index(v) if v in SOUL_TYPES else -1
            out.append(float(v))
        return out

    def predict(self, rows: list[dict]) -> list[float]:
        """Each row goes to its rank's model if there is one, else to this overall model."""
        out = [0.0] * len(rows)
        groups: dict[int, list[int]] = {}
        for i, r in enumerate(rows):
            groups.setdefault(int(r["tier"]), []).append(i)
        for tier, idx in groups.items():
            model = self.by_tier.get(tier, self)
            for i, p in zip(idx, model._predict([rows[i] for i in idx]), strict=True):
                out[i] = p
        return out

    def _predict(self, rows: list[dict]) -> list[float]:
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
