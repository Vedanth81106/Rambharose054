from pathlib import Path

import joblib
import numpy as np
import torch

from twin.ml_models.rul.model import GRURULRegressor


_MODEL_DIR = Path(__file__).parent

_MODEL_PATH = _MODEL_DIR / "rul_model.pt"
_SCALER_PATH = _MODEL_DIR / "rul_scaler.pkl"

FEATURES = [
    "rpm",
    "fuel_flow",
    "torque",
    "oil_temperature",
    "oil_pressure",
    "cht",
    "egt",
    "vibration",
]

SEQ_LEN = 50

_DEVICE = torch.device(
    "cuda"
    if torch.cuda.is_available()
    else "cpu"
)


_model = GRURULRegressor(
    n_features=len(FEATURES),
    hidden=96,
    layers=2,
    dropout=0.15,
)

_model.load_state_dict(
    torch.load(
        _MODEL_PATH,
        map_location=_DEVICE,
    )
)

_model.to(_DEVICE)
_model.eval()

_scaler = joblib.load(_SCALER_PATH)


def predict_rul(
    telemetry_window: list[dict],
) -> float | None:

    if len(telemetry_window) < SEQ_LEN:
        return None

    window = telemetry_window[-SEQ_LEN:]

    values = np.array(
        [
            [
                row[feature]
                for feature in FEATURES
            ]
            for row in window
        ],
        dtype=np.float32,
    )

    scaled = _scaler.transform(values)

    x = torch.tensor(
        scaled,
        dtype=torch.float32,
        device=_DEVICE,
    ).unsqueeze(0)

    with torch.no_grad():
        prediction = _model(x)

    return round(
        float(prediction.item()),
        2,
    )