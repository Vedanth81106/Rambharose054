"""Loads model_data/features.npz (written by prepare_data.py)."""

from pathlib import Path

import numpy as np

MODEL_DIR = Path(__file__).resolve().parent / "model_data"


def load():
    d = dict(np.load(MODEL_DIR / "features.npz", allow_pickle=True))
    d["split"] = d["run_split"][d["run"]]
    d["profile"] = d["run_profile"][d["run"]]
    d["feature_names"] = [str(n) for n in d["feature_names"]]
    return d


def runs_of(d, split):
    """Indices (into the run arrays) of the runs in a split."""
    return np.flatnonzero(d["run_split"] == split)
