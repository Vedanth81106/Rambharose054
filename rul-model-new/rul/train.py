import random
import numpy as np
import torch

SEED = 42

random.seed(SEED)
np.random.seed(SEED)
torch.manual_seed(SEED)
torch.cuda.manual_seed_all(SEED)

torch.backends.cudnn.deterministic = True
torch.backends.cudnn.benchmark = False

import json
from pathlib import Path
import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import TensorDataset, DataLoader

from model import GRURULRegressor


# ============================================================
# CONFIG
# ============================================================

# Written by prepare_data.py (run that first).
DATA_DIR = Path(__file__).resolve().parent / "rul_data"

MODEL_PATH = DATA_DIR / "rul_gru_best.pt"
ONNX_PATH = DATA_DIR / "rul_gru.onnx"   # what the backend loads (no PyTorch needed)

BATCH_SIZE = 32
LEARNING_RATE = 1e-3
MAX_EPOCHS = 50

PATIENCE = 8

DEVICE = torch.device(
    "cuda" if torch.cuda.is_available() else "cpu"
)

print("=" * 70)
print("RUL GRU TRAINING")
print("=" * 70)

print("Device:", DEVICE)

if DEVICE.type == "cuda":
    print("GPU:", torch.cuda.get_device_name(0))


# ============================================================
# LOAD DATA
# ============================================================

print("\nLoading data...")

X_train = np.load(f"{DATA_DIR}/X_train.npy")
y_train = np.load(f"{DATA_DIR}/y_train.npy")

X_val = np.load(f"{DATA_DIR}/X_val.npy")
y_val = np.load(f"{DATA_DIR}/y_val.npy")

print("X_train:", X_train.shape)
print("y_train:", y_train.shape)

print("X_val  :", X_val.shape)
print("y_val  :", y_val.shape)


# ============================================================
# TORCH DATASETS
# ============================================================

train_dataset = TensorDataset(
    torch.from_numpy(X_train),
    torch.from_numpy(y_train)
)

val_dataset = TensorDataset(
    torch.from_numpy(X_val),
    torch.from_numpy(y_val)
)


train_loader = DataLoader(
    train_dataset,
    batch_size=BATCH_SIZE,
    shuffle=True,
    num_workers=0,
    pin_memory=(DEVICE.type == "cuda")
)

val_loader = DataLoader(
    val_dataset,
    batch_size=BATCH_SIZE,
    shuffle=False,
    num_workers=0,
    pin_memory=(DEVICE.type == "cuda")
)


# ============================================================
# MODEL
# ============================================================

model = GRURULRegressor(
    n_features=X_train.shape[-1],
    hidden_size=64,
    num_layers=2,
    dropout=0.2
).to(DEVICE)


print("\nModel parameters:", sum(
    p.numel() for p in model.parameters()
))


# ============================================================
# LOSS
# ============================================================

criterion = nn.SmoothL1Loss(
    reduction="none"
)

optimizer = torch.optim.Adam(
    model.parameters(),
    lr=LEARNING_RATE
)


# ============================================================
# TRAINING
# ============================================================

best_val_rmse = float("inf")
epochs_without_improvement = 0


for epoch in range(1, MAX_EPOCHS + 1):

    # --------------------------------------------------------
    # TRAIN
    # --------------------------------------------------------

    model.train()

    train_loss = 0.0
    train_samples = 0

    for X_batch, y_batch in train_loader:

        X_batch = X_batch.to(
            DEVICE,
            non_blocking=True
        )

        y_batch = y_batch.to(
            DEVICE,
            non_blocking=True
        )

        optimizer.zero_grad()

        predictions = model(X_batch)

        # Huber loss
        losses = criterion(
            predictions,
            y_batch
        )

        # Give extra importance to RUL < 600 seconds.
        #
        # y = 1.0 -> 600 seconds
        # y < 1.0 -> inside failure horizon
        #
        # Weight ranges from 1 to 3.
        weights = 1.0 + 2.0 * (
            1.0 - y_batch
        )

        loss = (
            losses * weights
        ).mean()

        loss.backward()

        # Prevent exploding gradients
        torch.nn.utils.clip_grad_norm_(
            model.parameters(),
            max_norm=1.0
        )

        optimizer.step()

        train_loss += (
            loss.item() * X_batch.size(0)
        )

        train_samples += X_batch.size(0)

    train_loss /= train_samples


    # --------------------------------------------------------
    # VALIDATION
    # --------------------------------------------------------

    model.eval()

    val_squared_error = 0.0
    val_count = 0

    in_horizon_squared_error = 0.0
    in_horizon_count = 0

    with torch.no_grad():

        for X_batch, y_batch in val_loader:

            X_batch = X_batch.to(
                DEVICE,
                non_blocking=True
            )

            y_batch = y_batch.to(
                DEVICE,
                non_blocking=True
            )

            predictions = model(X_batch)

            # Convert normalized RUL back to seconds
            pred_seconds = predictions * 600.0
            true_seconds = y_batch * 600.0

            squared_error = (
                pred_seconds - true_seconds
            ) ** 2

            val_squared_error += (
                squared_error.sum().item()
            )

            val_count += X_batch.size(0)

            # RUL < 600 seconds
            mask = y_batch < 1.0

            if mask.any():

                in_horizon_squared_error += (
                    squared_error[mask]
                    .sum()
                    .item()
                )

                in_horizon_count += (
                    mask.sum().item()
                )


    val_rmse = (
        val_squared_error / val_count
    ) ** 0.5

    if in_horizon_count > 0:

        in_horizon_rmse = (
            in_horizon_squared_error
            / in_horizon_count
        ) ** 0.5

    else:

        in_horizon_rmse = float("nan")


    # --------------------------------------------------------
    # PRINT
    # --------------------------------------------------------

    print(
        f"Epoch {epoch:02d}/{MAX_EPOCHS} | "
        f"Train Loss: {train_loss:.5f} | "
        f"Val RMSE: {val_rmse:.2f}s | "
        f"In-Horizon RMSE: {in_horizon_rmse:.2f}s"
    )


    # --------------------------------------------------------
    # EARLY STOPPING
    # --------------------------------------------------------

    if in_horizon_rmse < best_val_rmse:

        best_val_rmse = in_horizon_rmse

        epochs_without_improvement = 0

        torch.save(
            {
                "model_state_dict": model.state_dict(),
                "n_features": X_train.shape[-1],
                "hidden_size": 64,
                "num_layers": 2,
                "dropout": 0.2,
                "best_val_rmse": best_val_rmse
            },
            MODEL_PATH
        )

        print(
            f"  ✅ Saved best model "
            f"({best_val_rmse:.2f}s)"
        )

    else:

        epochs_without_improvement += 1

        if epochs_without_improvement >= PATIENCE:

            print(
                "\nEarly stopping."
            )

            break


# ============================================================
# FINAL
# ============================================================

print("\n" + "=" * 70)
print("TRAINING COMPLETE")
print("=" * 70)

print(
    "Best validation in-horizon RMSE:",
    f"{best_val_rmse:.2f}s"
)

print(
    "Model saved to:",
    MODEL_PATH
)


# ============================================================
# EXPORT BEST MODEL TO ONNX
# ============================================================

checkpoint = torch.load(MODEL_PATH, map_location="cpu", weights_only=False)
model = model.cpu()
model.load_state_dict(checkpoint["model_state_dict"])
model.eval()

torch.onnx.export(
    model,
    torch.zeros(1, X_train.shape[1], X_train.shape[2]),
    ONNX_PATH,
    input_names=["sequence"],
    output_names=["rul_fraction"],          # RUL / 600, in 0-1
    dynamic_axes={"sequence": {0: "batch"}, "rul_fraction": {0: "batch"}},
    dynamo=False,
)

print("ONNX model saved to:", ONNX_PATH)