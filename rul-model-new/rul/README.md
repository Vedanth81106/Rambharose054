# RUL model: data prep, training, evaluation

Fixed version of the RUL scripts. Same GRU and training loop as before; the
data preparation now covers the fast faults (misfire, overheating, oil
pressure, fuel starvation), which the old 300 s windows left out.

## Setup

```bash
pip install torch numpy pandas onnx onnxruntime
```

Point the scripts at the unzipped dataset (the folder with `runs.csv` and `runs/`):

```bash
export SIM_V2_DIR="/path/to/sim_v2"          # Windows (PowerShell): $env:SIM_V2_DIR="C:\path\to\sim_v2"
```

(Without it they look for `data/sim_v2` two folders above this one, i.e. in the project repo.)

## Run, from this folder

```bash
python prepare_data.py    # dataset -> rul_data/ (training samples + scaler.json); ~2 GB free RAM
python train.py           # trains, saves rul_data/rul_gru_best.pt and rul_data/rul_gru.onnx (uses the GPU if there is one)
python eval.py            # test-split metrics (RUL_MODEL_GUIDE.md §7) + rul_data/test_predictions.csv
```

## Send back

- `rul_data/rul_gru.onnx`
- `rul_data/scaler.json`
- the output printed by `eval.py`

Not the `.npy` files.

## Files

- `rul_features.py`: the 35 input features. The backend uses this same code live, so don't compute features anywhere else.
- `prepare_data.py`: 180 s sequences, left-padded so samples start at 90 s; stride 3 inside the failure horizon, 10 elsewhere; scaler fitted on the training rows.
- `train.py`, `model.py`: unchanged model and loop; exports ONNX at the end.
- `eval.py`: scores the ONNX model on every second of every test run.
