"""Train the fault classifier (XGBoost, 10 classes).

Run after prepare_data.py:  python train_classifier.py
Writes model_data/xgboost_classifier.json.

- Class weights, so the rarer fault rows count as much as healthy ones.
- Rows with 0 < severity < 0.05 are left out of training: a fault that
  weak is physically indistinguishable from healthy (guide §7.2). They
  stay in the evaluation.
- 300 trees max with early stopping on the validation runs: ~1 MB instead
  of 16 MB, and fast enough to score every second live.
"""

import numpy as np
import pandas as pd
import xgboost as xgb

from common import MODEL_DIR, load


def main():
    d = load()
    X = pd.DataFrame(d["X"], columns=d["feature_names"])
    y, sev = d["fault_id"], d["severity"]
    train = (d["split"] == "train") & ~((sev > 0) & (sev < 0.05))
    val = d["split"] == "val"

    counts = np.bincount(y[train], minlength=10)
    weight = (len(y[train]) / (10 * counts))[y[train]]

    model = xgb.XGBClassifier(
        n_estimators=300,
        max_depth=6,
        learning_rate=0.1,
        subsample=0.8,
        colsample_bytree=0.8,
        tree_method="hist",
        objective="multi:softprob",
        eval_metric="mlogloss",
        early_stopping_rounds=30,
        random_state=42,
    )
    model.fit(X[train], y[train], sample_weight=weight, eval_set=[(X[val], y[val])], verbose=50)

    path = MODEL_DIR / "xgboost_classifier.json"
    model.save_model(path)
    print(f"Best iteration {model.best_iteration}; saved to {path}")


if __name__ == "__main__":
    main()
