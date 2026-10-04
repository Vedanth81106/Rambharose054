"""Evaluate both models on the test runs, the way the backend runs them.

Run after both training scripts:  python eval.py

- Classifier: class probabilities averaged over the last 20 s.
- Autoencoder: forward pass in plain numpy from autoencoder.json (as the
  backend does), alarm when 5 of the last 10 scores exceed the threshold.
Targets (guide §8): F1 >= 0.9 per class, < 1 false alarm per hour, 0 missed faults.
"""

import json

import numpy as np
import pandas as pd
import xgboost as xgb

from common import MODEL_DIR, load, runs_of

SMOOTH_S = 20
DETECT_HOLD_S = 10            # "detected" = correct for 10 s in a row


def autoencoder_scores(ae, X):
    z = (np.nan_to_num(X) - np.array(ae["scaler_mean"])) / np.array(ae["scaler_scale"])
    h = z
    for layer in ae["layers"]:
        h = h @ np.array(layer["kernel"]) + np.array(layer["bias"])
        if layer["activation"] == "relu":
            h = np.maximum(h, 0.0)
    return ((z - h) ** 2).mean(axis=1)


def first_hold(flags, start, hold):
    n = 0
    for i in range(start, len(flags)):
        n = n + 1 if flags[i] else 0
        if n >= hold:
            return i - hold + 1
    return None


def alarms(flags, hold):
    """Alarm episodes: runs of >= hold consecutive flags."""
    n = count = 0
    for f in flags:
        n = n + 1 if f else 0
        count += n == hold
    return count


def main():
    d = load()
    names = d["feature_names"]
    booster = xgb.Booster()
    booster.load_model(MODEL_DIR / "xgboost_classifier.json")
    ae = json.loads((MODEL_DIR / "autoencoder.json").read_text())
    assert booster.feature_names == names and ae["features"] == names, "feature list mismatch"
    window, min_over = ae["persistence"]["window"], ae["persistence"]["min_over"]

    cm = np.zeros((10, 10), int)
    rows = []
    for r in runs_of(d, "test"):
        m = d["run"] == r
        X, y, sev, t = d["X"][m], d["fault_id"][m], d["severity"][m], d["sim_time"][m]
        fault, onset = int(d["run_fault"][r]), d["run_onset"][r]
        failure, profile = d["run_failure"][r], d["run_profile"][r]

        probs = booster.predict(xgb.DMatrix(X, feature_names=names))
        cls = pd.DataFrame(probs).rolling(SMOOTH_S, min_periods=1).mean().to_numpy().argmax(1)
        over = autoencoder_scores(ae, X) > ae["threshold"]
        ae_alarm = pd.Series(over.astype(float)).rolling(window, min_periods=1).sum().to_numpy() >= min_over

        scored = (sev >= 0.25) | (y == 0)
        np.add.at(cm, (y[scored], cls[scored]), 1)

        healthy = y == 0
        start = int(np.argmax(t >= onset)) if fault else len(t)
        cls_det = first_hold(cls == fault, start, DETECT_HOLD_S) if fault else None
        ae_det = first_hold(ae_alarm, start, 1) if fault else None
        rows.append(dict(
            fault=fault, profile=profile, healthy_s=int(healthy.sum()),
            cls_alarms=alarms((cls != 0) & healthy, DETECT_HOLD_S),
            ae_flag=int((over & healthy).sum()), ae_alarms=alarms(ae_alarm & healthy, 1),
            cls_delay=None if cls_det is None else t[cls_det] - onset,
            ae_delay=None if ae_det is None else t[ae_det] - onset,
            ae_lead=None if ae_det is None or np.isnan(failure) else (failure - t[ae_det]) / (failure - onset),
        ))

    R = pd.DataFrame(rows)
    hours = R.healthy_s.sum() / 3600
    f1 = [2 * cm[k, k] / max(cm[:, k].sum() + cm[k].sum(), 1) for k in range(10)]
    F = R[R.fault != 0]

    print("=" * 70)
    print("FAULT CLASSIFIER (20 s averaged probabilities)")
    print("=" * 70)
    print("F1 per class (severity >= 0.25):", {k: round(v, 3) for k, v in enumerate(f1)})
    print(f"False alarms on healthy flight: {R.cls_alarms.sum() / hours:.2f} per hour")
    print("Missed faults:", int(F.cls_delay.isna().sum()))
    print("Detection delay per fault (s):", F.groupby("fault").cls_delay.mean().round(0).to_dict())
    print("Confusion matrix (rows = true, columns = predicted):")
    print(cm)

    print()
    print("=" * 70)
    print(f"AUTOENCODER (threshold {ae['threshold']:.4f}, alarm = {min_over} of last {window} over)")
    print("=" * 70)
    print(f"Healthy samples over threshold: {R.ae_flag.sum() / R.healthy_s.sum():.2%}")
    print(f"False alarms on healthy flight: {R.ae_alarms.sum() / hours:.2f} per hour")
    by_profile = R.groupby("profile")[["healthy_s", "ae_alarms"]].sum()
    by_profile["alarms_per_hour"] = (by_profile.ae_alarms / (by_profile.healthy_s / 3600)).round(2)
    print(by_profile.alarms_per_hour.to_string())
    print("Missed faults:", int(F.ae_delay.isna().sum()))
    print("Detection delay per fault (s):", F.groupby("fault").ae_delay.mean().round(0).to_dict())
    print("Lead time (share of onset -> failure left):", F.groupby("fault").ae_lead.mean().round(2).to_dict())


if __name__ == "__main__":
    main()
