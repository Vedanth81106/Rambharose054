"""Build RUL training sequences from the sim_v2 dataset.

Run:  python prepare_data.py   (set SIM_V2_DIR to the dataset folder; see README.md)

Changes from the first version (which left the fast faults out of training):
- Sequences are left-padded, so samples end from WARMUP + ROLL seconds on.
  Before, a sample needed 300 s of history after warm-up, so the first one
  ended at ~388 s, after most misfire / overheating / oil pressure / fuel
  starvation runs had already failed.
- 180 s sequences (RUL_MODEL_GUIDE.md §5 allows 180-300).
- Denser samples inside the failure horizon (stride 3 vs 10).
- RPM roughness on the residual, roughness as in the guide (rul_features.py).
- The scaler is fitted on the training rows themselves (not on padded windows).
"""

import json
import os
from pathlib import Path

import numpy as np
import pandas as pd

from rul_features import (
    FEATURE_COLUMNS, ROLL, SEQ_LEN, WARMUP, build_features, sequence_ending_at,
)


ROOT = Path(__file__).resolve().parents[2]
# The unzipped dataset folder (contains runs.csv and runs/). Default: data/sim_v2 in
# the repo; set SIM_V2_DIR to use another location.
DATA_DIR = Path(os.environ.get("SIM_V2_DIR", ROOT / "data" / "sim_v2"))
OUTPUT_DIR = Path(__file__).resolve().parent / "rul_data"

STRIDE = 10                   # samples with RUL at the 600 s cap
STRIDE_HORIZON = 3            # samples with RUL < 600 s
FIRST_END = WARMUP + ROLL     # earliest sample end (s): rolling features filled


def run_samples(df):
    """(features, sample end rows, labels) for one run."""

    features = build_features(df).to_numpy(dtype=np.float32)
    t = df["sim_time"].to_numpy()
    rul = df["rul_seconds"].to_numpy(dtype=np.float32)

    ends, last = [], None
    for i in np.flatnonzero(t >= FIRST_END):
        stride = STRIDE_HORIZON if rul[i] < 600 else STRIDE
        if last is None or i - last >= stride:
            ends.append(i)
            last = i
    return features, np.array(ends), rul / 600.0


def build_split(run_ids):
    """Sequences, labels and the split's feature rows (for the scaler).

    Filled into one preallocated float32 array: building a list of windows
    and converting it holds the data twice (~3 GB peak for train).
    """

    per_run = []
    for run_id in run_ids:
        df = pd.read_csv(DATA_DIR / "runs" / f"{run_id}.csv")
        features, ends, target = run_samples(df)
        rows = features[df["sim_time"].to_numpy() >= WARMUP]
        per_run.append((features, ends, target[ends], rows))

    total = sum(len(ends) for _, ends, _, _ in per_run)
    X = np.empty((total, SEQ_LEN, len(FEATURE_COLUMNS)), dtype=np.float32)
    y = np.empty(total, dtype=np.float32)
    i = 0
    for features, ends, labels, _ in per_run:
        for e in ends:
            X[i] = sequence_ending_at(features, e)
            i += 1
        y[i - len(ends):i] = labels
    rows = np.concatenate([r for _, _, _, r in per_run])
    return X, y, rows


def main():
    OUTPUT_DIR.mkdir(exist_ok=True)
    runs = pd.read_csv(DATA_DIR / "runs.csv")
    print(f"Runs: {len(runs)}, features: {len(FEATURE_COLUMNS)}, sequence: {SEQ_LEN} s")

    splits = {}
    for split in ("train", "val", "test"):
        ids = runs.loc[runs["split"] == split, "run_id"].tolist()
        splits[split] = build_split(ids)
        X, y, _ = splits[split]
        print(f"{split:5s}: {X.shape}, in horizon {(y < 1).mean():.1%}")

    # Standardise with training statistics only.
    rows = splits["train"][2].astype(np.float64)
    mean = rows.mean(axis=0)
    std = rows.std(axis=0)
    std[std < 1e-8] = 1.0

    mean32, std32 = mean.astype(np.float32), std.astype(np.float32)
    for split, (X, y, _) in splits.items():
        X -= mean32                 # in place: no float64 copy
        X /= std32
        if not np.isfinite(X).all():
            raise ValueError(f"{split} has NaN or inf features")
        np.save(OUTPUT_DIR / f"X_{split}.npy", X)
        np.save(OUTPUT_DIR / f"y_{split}.npy", y)

    scaler = {
        "feature_names": FEATURE_COLUMNS,
        "n_features": len(FEATURE_COLUMNS),
        "sequence_length": SEQ_LEN,
        "warmup": WARMUP,
        "mean": mean.tolist(),
        "std": std.tolist(),
    }
    (OUTPUT_DIR / "scaler.json").write_text(json.dumps(scaler, indent=2))
    print(f"Saved to {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
