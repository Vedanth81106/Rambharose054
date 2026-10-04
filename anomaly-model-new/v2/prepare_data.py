"""Compute the fault features for every dataset run, once.

Run:  python prepare_data.py   (set SIM_V2_DIR to the dataset folder; see README.md)

Writes model_data/features.npz: one row per sample from t = 60 s (the
twin scores nothing during warm-up), with the labels and run info the
training and evaluation scripts need.
"""

import os
from pathlib import Path

import numpy as np
import pandas as pd

from fault_features import FEATURE_COLUMNS, build_fault_features


HERE = Path(__file__).resolve().parent
DATA_DIR = Path(os.environ.get("SIM_V2_DIR", HERE.parents[1] / "data" / "sim_v2"))
OUTPUT_DIR = HERE / "model_data"
WARMUP = 60


def main():
    OUTPUT_DIR.mkdir(exist_ok=True)
    runs = pd.read_csv(DATA_DIR / "runs.csv")
    print(f"Runs: {len(runs)}, features: {len(FEATURE_COLUMNS)}")

    parts = []
    for i, r in enumerate(runs.itertuples()):
        df = pd.read_csv(DATA_DIR / "runs" / f"{r.run_id}.csv")
        X = build_fault_features(df)
        keep = (df["sim_time"] >= WARMUP).to_numpy()
        parts.append(dict(
            X=X.to_numpy(dtype=np.float32)[keep],
            fault_id=df["fault_id"].to_numpy()[keep],
            severity=df["severity"].to_numpy(dtype=np.float32)[keep],
            sim_time=df["sim_time"].to_numpy(dtype=np.float32)[keep],
            run=np.full(keep.sum(), i, dtype=np.int32),
        ))
        if (i + 1) % 50 == 0:
            print(f"  {i + 1}/{len(runs)} runs")

    out = {k: np.concatenate([p[k] for p in parts]) for k in parts[0]}
    np.savez_compressed(
        OUTPUT_DIR / "features.npz",
        **out,
        feature_names=np.array(FEATURE_COLUMNS),
        run_id=runs["run_id"].to_numpy(),
        run_split=runs["split"].to_numpy(),
        run_profile=runs["profile"].to_numpy(),
        run_fault=runs["fault_id"].to_numpy(),
        run_onset=runs["onset_s"].to_numpy(dtype=float),
        run_failure=runs["failure_s"].to_numpy(dtype=float),
    )
    print(f"Saved {len(out['X'])} rows to {OUTPUT_DIR / 'features.npz'}")


if __name__ == "__main__":
    main()
