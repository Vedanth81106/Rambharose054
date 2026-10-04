"""Train the anomaly detector: a dense autoencoder on healthy rows only.

Run after prepare_data.py:  python train_autoencoder.py
Writes model_data/autoencoder.json (weights, scaler, threshold), which the
backend runs with plain numpy: no TensorFlow or PyTorch needed.

- Healthy rows = fault-0 runs plus every run before its fault's onset,
  from t = 60 s, in ALL profiles. Warm-up (60-120 s) and rapid throttle are
  included: the live twin sees both, and leaving them out of training is
  what made the previous version flag them.
- Score = mean squared reconstruction error of the standardised features.
- Threshold = the 99.5th percentile of the score on healthy validation
  rows (guide §7.1). The backend alarms only when 5 of the last 10 scores
  exceed it (persistence), which eval.py applies too.
"""

import json
import warnings

import numpy as np
from sklearn.exceptions import ConvergenceWarning
from sklearn.neural_network import MLPRegressor
from sklearn.preprocessing import StandardScaler

from common import MODEL_DIR, load

HIDDEN = (32, 16, 8, 16, 32)  # 8-number bottleneck (guide §7.1: 64-32-8 encoder; smaller suits 32 features)
THRESHOLD_PERCENTILE = 99.5
PERSISTENCE = {"window": 10, "min_over": 5}


def reconstruction_error(model, Z):
    return ((Z - model.predict(Z)) ** 2).mean(axis=1)


def main():
    d = load()
    X = np.nan_to_num(d["X"])
    healthy = d["fault_id"] == 0
    train = healthy & (d["split"] == "train")
    val = healthy & (d["split"] == "val")
    print(f"Healthy rows: train {train.sum()}, val {val.sum()}")

    scaler = StandardScaler().fit(X[train])
    Z_train, Z_val = scaler.transform(X[train]), scaler.transform(X[val])

    model = MLPRegressor(
        hidden_layer_sizes=HIDDEN,
        activation="relu",
        solver="adam",
        batch_size=256,
        learning_rate_init=1e-3,
        max_iter=200,
        early_stopping=True,
        n_iter_no_change=10,
        random_state=42,
        verbose=True,
    )
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", ConvergenceWarning)
        model.fit(Z_train, Z_train)

    threshold = float(np.percentile(reconstruction_error(model, Z_val), THRESHOLD_PERCENTILE))
    print(f"Threshold ({THRESHOLD_PERCENTILE}th percentile of healthy val): {threshold:.4f}")

    layers = [
        {
            "kernel": W.tolist(),
            "bias": b.tolist(),
            "activation": "linear" if i == len(model.coefs_) - 1 else "relu",
        }
        for i, (W, b) in enumerate(zip(model.coefs_, model.intercepts_))
    ]
    out = {
        "features": d["feature_names"],
        "scaler_mean": scaler.mean_.tolist(),
        "scaler_scale": scaler.scale_.tolist(),
        "threshold": threshold,
        "persistence": PERSISTENCE,
        "layers": layers,
    }
    path = MODEL_DIR / "autoencoder.json"
    path.write_text(json.dumps(out))
    print(f"Saved to {path}")


if __name__ == "__main__":
    main()
