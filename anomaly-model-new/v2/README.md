# Anomaly detector + fault classifier: v2 training

Everything needed to train both fault models and get them into the twin.
What changed from v1:

- **One feature file** (`fault_features.py`), copied unchanged into the backend, so live features can't differ from training. Don't compute features anywhere else.
- **9 more window features** (RPM median / percentiles / std / skew / dip fraction, EGT median, torque mean, 30 s vibration RMS). In testing they cut misfire↔instability confusion from 114 windows to 1 (misfire F1 0.88 → 0.997).
- **`fuel_ratio` = measured ÷ commanded fuel** (guide §5.3), not fuel flow ÷ pulse width.
- **Classifier:** class weights, near-zero-severity rows left out of training, 300 trees max with early stopping (≈1 MB instead of 16 MB).
- **Autoencoder:** scikit-learn (no TensorFlow), trained on healthy rows from **all** profiles **including** warm-up and rapid throttle, which is what v1 false-alarmed on. Threshold from healthy validation rows; alarm = 5 of the last 10 scores over it. Saved as JSON.

## Setup

```bash
pip install numpy pandas scikit-learn xgboost
```

Point the scripts at the unzipped dataset (the folder with `runs.csv` and `runs/`):

```bash
export SIM_V2_DIR="/path/to/sim_v2"          # Windows (PowerShell): $env:SIM_V2_DIR="C:\path\to\sim_v2"
```

## Run, from this folder

```bash
python prepare_data.py        # features for every run -> model_data/features.npz (a few minutes, < 1 GB RAM)
python train_classifier.py    # -> model_data/xgboost_classifier.json
python train_autoencoder.py   # -> model_data/autoencoder.json
python eval.py                # test-split results for both models
```

## Targets (eval.py prints these)

| | Target |
|---|---|
| Classifier F1, every class | ≥ 0.9 |
| False alarms on healthy flight (both models) | < 1 per hour |
| Missed faults | 0 |

If the autoencoder misses a target, tune `HIDDEN` or `THRESHOLD_PERCENTILE` in `train_autoencoder.py` and re-run it and `eval.py`. Don't change the features without telling us: the backend uses the same file.

## Send back

- `model_data/xgboost_classifier.json`
- `model_data/autoencoder.json`
- the output printed by `eval.py`

Not `features.npz`.
