"""Evaluate the exported RUL model on the test runs (RUL_MODEL_GUIDE.md §7).

Run after train.py:  python eval.py   (set SIM_V2_DIR as for prepare_data.py)

Scores the ONNX file (what the backend loads) on every second of every test
run, one run at a time, with the post-processing the backend applies
(clamp to 0-600, ~5 s exponential smoothing).
"""

import json
import os
from pathlib import Path

import numpy as np
import onnxruntime as ort
import pandas as pd

from rul_features import WARMUP, ROLL, build_features, sequence_ending_at


ROOT = Path(__file__).resolve().parents[2]
# The unzipped dataset folder (contains runs.csv and runs/). Default: data/sim_v2 in
# the repo; set SIM_V2_DIR to use another location.
DATA_DIR = Path(os.environ.get("SIM_V2_DIR", ROOT / "data" / "sim_v2"))
MODEL_DIR = Path(__file__).resolve().parent / "rul_data"
MAX_RUL = 600.0
SMOOTH_HALFLIFE_S = 5


def predict_run(session, scaler, df):
    """Smoothed RUL prediction (s) for every sample from WARMUP + ROLL on."""

    features = build_features(df).to_numpy(dtype=np.float32)
    features = (features - np.array(scaler["mean"], dtype=np.float32)) / np.array(
        scaler["std"], dtype=np.float32
    )
    ends = np.flatnonzero(df["sim_time"].to_numpy() >= WARMUP + ROLL)
    preds = []
    for chunk in np.array_split(ends, max(1, len(ends) // 256)):
        batch = np.stack([sequence_ending_at(features, e) for e in chunk])
        preds.append(session.run(None, {"sequence": batch})[0])
    raw = np.clip(np.concatenate(preds) * MAX_RUL, 0, MAX_RUL)
    smooth = pd.Series(raw).ewm(halflife=SMOOTH_HALFLIFE_S).mean().to_numpy()
    return ends, smooth


def main():
    scaler = json.loads((MODEL_DIR / "scaler.json").read_text())
    session = ort.InferenceSession(str(MODEL_DIR / "rul_gru.onnx"))
    runs = pd.read_csv(DATA_DIR / "runs.csv")
    test = runs[runs["split"] == "test"]

    rows, timeliness = [], []
    for _, r in test.iterrows():
        df = pd.read_csv(DATA_DIR / "runs" / f"{r.run_id}.csv")
        ends, pred = predict_run(session, scaler, df)
        t = df["sim_time"].to_numpy()[ends]
        y = df["rul_seconds"].to_numpy()[ends]
        rows.append(pd.DataFrame({
            "run": r.run_id, "fault": r.fault_id, "profile": r.profile,
            "t": t, "true": y, "pred": pred,
            "onset": r.onset_s, "failure": r.failure_s,
        }))

        # Warning timeliness: first prediction < 300 s vs when true RUL < 300 s.
        if not np.isnan(r.failure_s):
            true_cross = t[np.argmax(y < 300)] if (y < 300).any() else None
            pred_cross = t[np.argmax(pred < 300)] if (pred < 300).any() else None
            if true_cross is not None:
                timeliness.append(
                    np.nan if pred_cross is None else pred_cross - true_cross
                )

    R = pd.concat(rows, ignore_index=True)
    R["err"] = R.pred - R.true
    horizon = R[R.true < MAX_RUL]
    last120 = R[R.failure.notna() & (R.failure - R.t <= 120) & (R.t <= R.failure)]
    healthy = R[(R.true >= MAX_RUL) & ((R.fault == 0) | (R.t < R.onset) | R.failure.isna())]
    never_fail = R[R.failure.isna() & (R.fault != 0)]
    d = R.err / 10.0
    asym = np.where(d < 0, np.exp(-d / 13) - 1, np.exp(d / 10) - 1)
    rmse = lambda e: float(np.sqrt(np.mean(e ** 2))) if len(e) else float("nan")
    tl = np.array(timeliness, dtype=float)

    print("=" * 70)
    print("RUL TEST RESULTS (every second of every test run)")
    print("=" * 70)
    print(f"RMSE in horizon (true RUL < 600 s): {rmse(horizon.err):6.1f} s")
    print(f"RMSE last 120 s before failure    : {rmse(last120.err):6.1f} s")
    print(f"Asymmetric score (mean, lower=better): {asym.mean():.2f}")
    print(f"False countdowns (healthy rows < 400 s): {(healthy.pred < 400).mean():.2%}")
    print(f"Never-failing fault runs predicted < 400 s: {(never_fail.pred < 400).mean():.2%}")
    print(
        f"Warning (<300 s) timeliness: median {np.nanmedian(tl):+.0f} s, "
        f"late by > 30 s: {int((tl > 30).sum())}/{len(tl)}, never warned: {int(np.isnan(tl).sum())}"
    )

    print("\nIn-horizon RMSE per fault (s):")
    print(horizon.groupby("fault").err.apply(rmse).round(0).to_string())
    print("\nIn-horizon RMSE per profile (s):")
    print(horizon.groupby("profile").err.apply(rmse).round(0).to_string())

    along = []
    for run, g in R[R.failure.notna()].groupby("run"):
        on, fl = g.onset.iloc[0], g.failure.iloc[0]
        for q in (0.25, 0.5, 0.75):
            i = (g.t - (on + q * (fl - on))).abs().idxmin()
            along.append((q, abs(R.err[i])))
    print("\nMean |error| at 25 / 50 / 75 % of onset -> failure (s):")
    print(pd.DataFrame(along, columns=["q", "abs_err"]).groupby("q").abs_err.mean().round(0).to_string())

    R.to_csv(MODEL_DIR / "test_predictions.csv", index=False)
    print(f"\nPer-second predictions saved to {MODEL_DIR / 'test_predictions.csv'}")


if __name__ == "__main__":
    main()
