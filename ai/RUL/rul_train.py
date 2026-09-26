import numpy as np
import pandas as pd
import torch
import torch.nn as nn

from torch.utils.data import Dataset, DataLoader
from sklearn.preprocessing import StandardScaler
import joblib

from rul_model import GRURULRegressor


# ============================================================
# CONFIG
# ============================================================

CSV_PATH = "engine_rul_training_dataset.csv"

FEATURES = [
    "RPM",
    "FuelFlow",
    "Torque",
    "OilTemp",
    "OilPressure",
    "CHT",
    "EGT",
    "Vibration"
]

TARGET = "RUL_hours"

SEQ_LEN = 50

BATCH_SIZE = 256

EPOCHS = 30

LEARNING_RATE = 1e-3

DEVICE = (
    torch.device("cuda")
    if torch.cuda.is_available()
    else torch.device("cpu")
)

print("Device:", DEVICE)


# ============================================================
# LOAD DATASET
# ============================================================

print("\nLoading dataset...")

df = pd.read_csv(CSV_PATH)

print("Rows:", len(df))
print("Columns:", len(df))

print("\nFaults:")
print(df["FaultID"].value_counts().sort_index())

print("\nRuns:", df["RunID"].nunique())


# ============================================================
# SPLIT BY RUN
# ============================================================

runs = sorted(df["RunID"].unique())

rng = np.random.default_rng(42)

rng.shuffle(runs)

n_runs = len(runs)

train_runs = runs[:12]
val_runs = runs[12:16]
test_runs = runs[16:20]

print("\nRun split:")
print("Train:", train_runs)
print("Validation:", val_runs)
print("Test:", test_runs)


train_df = df[df["RunID"].isin(train_runs)].copy()

val_df = df[df["RunID"].isin(val_runs)].copy()

test_df = df[df["RunID"].isin(test_runs)].copy()


# ============================================================
# SCALE FEATURES
# ============================================================

scaler = StandardScaler()

train_df.loc[:, FEATURES] = scaler.fit_transform(
    train_df[FEATURES]
)

val_df.loc[:, FEATURES] = scaler.transform(
    val_df[FEATURES]
)

test_df.loc[:, FEATURES] = scaler.transform(
    test_df[FEATURES]
)

joblib.dump(
    scaler,
    "rul_scaler.pkl"
)

print("\nScaler saved: rul_scaler.pkl")


# ============================================================
# SEQUENCE DATASET
# ============================================================

class RULDataset(Dataset):

    def __init__(
        self,
        dataframe,
        features,
        target,
        seq_len
    ):

        self.X = []
        self.y = []

        # IMPORTANT:
        # sequences are created separately for each RunID

        for run_id in sorted(
            dataframe["RunID"].unique()
        ):

            run = dataframe[
                dataframe["RunID"] == run_id
            ].sort_values("Time")

            X = run[features].values.astype(
                np.float32
            )

            y = run[target].values.astype(
                np.float32
            )

            for i in range(
                0,
                len(X) - seq_len + 1
            ):

                self.X.append(
                    X[i:i + seq_len]
                )

                # Predict RUL at final timestep
                self.y.append(
                    y[i + seq_len - 1]
                )

        self.X = np.asarray(
            self.X,
            dtype=np.float32
        )

        self.y = np.asarray(
            self.y,
            dtype=np.float32
        )

        print(
            f"Created {len(self.X)} sequences"
        )

    def __len__(self):
        return len(self.X)

    def __getitem__(self, index):

        return (
            torch.tensor(self.X[index]),
            torch.tensor(self.y[index])
        )


# ============================================================
# CREATE DATASETS
# ============================================================

print("\nCreating sequences...")

train_dataset = RULDataset(
    train_df,
    FEATURES,
    TARGET,
    SEQ_LEN
)

val_dataset = RULDataset(
    val_df,
    FEATURES,
    TARGET,
    SEQ_LEN
)

test_dataset = RULDataset(
    test_df,
    FEATURES,
    TARGET,
    SEQ_LEN
)


# ============================================================
# DATALOADERS
# ============================================================

train_loader = DataLoader(
    train_dataset,
    batch_size=BATCH_SIZE,
    shuffle=True,
    num_workers=0
)

val_loader = DataLoader(
    val_dataset,
    batch_size=BATCH_SIZE,
    shuffle=False,
    num_workers=0
)

test_loader = DataLoader(
    test_dataset,
    batch_size=BATCH_SIZE,
    shuffle=False,
    num_workers=0
)


# ============================================================
# MODEL
# ============================================================

model = GRURULRegressor(
    n_features=len(FEATURES),
    hidden=96,
    layers=2,
    dropout=0.15
)

model.to(DEVICE)

print("\nModel:")
print(model)


# ============================================================
# LOSS / OPTIMIZER
# ============================================================

criterion = nn.HuberLoss()

optimizer = torch.optim.AdamW(
    model.parameters(),
    lr=LEARNING_RATE,
    weight_decay=1e-4
)


# ============================================================
# VALIDATION FUNCTION
# ============================================================

def evaluate(model, loader):

    model.eval()

    total_loss = 0.0

    predictions = []
    targets = []

    with torch.no_grad():

        for X, y in loader:

            X = X.to(DEVICE)
            y = y.to(DEVICE)

            pred = model(X)

            loss = criterion(
                pred,
                y
            )

            total_loss += (
                loss.item() * len(X)
            )

            predictions.append(
                pred.cpu().numpy()
            )

            targets.append(
                y.cpu().numpy()
            )

    predictions = np.concatenate(
        predictions
    )

    targets = np.concatenate(
        targets
    )

    avg_loss = (
        total_loss /
        len(loader.dataset)
    )

    mae = np.mean(
        np.abs(
            predictions - targets
        )
    )

    rmse = np.sqrt(
        np.mean(
            (predictions - targets) ** 2
        )
    )

    return avg_loss, mae, rmse


# ============================================================
# TRAINING LOOP
# ============================================================

best_val_mae = float("inf")


print("\n============================================")
print("             TRAINING STARTED")
print("============================================")


for epoch in range(EPOCHS):

    model.train()

    total_loss = 0.0

    for X, y in train_loader:

        X = X.to(DEVICE)
        y = y.to(DEVICE)

        prediction = model(X)

        loss = criterion(
            prediction,
            y
        )

        optimizer.zero_grad()

        loss.backward()

        # Prevent exploding gradients
        torch.nn.utils.clip_grad_norm_(
            model.parameters(),
            1.0
        )

        optimizer.step()

        total_loss += (
            loss.item() * len(X)
        )

    train_loss = (
        total_loss /
        len(train_loader.dataset)
    )

    val_loss, val_mae, val_rmse = evaluate(
        model,
        val_loader
    )

    print(
        f"Epoch {epoch + 1:02d}/{EPOCHS} | "
        f"Train Loss: {train_loss:.5f} | "
        f"Val Loss: {val_loss:.5f} | "
        f"Val MAE: {val_mae:.4f} h | "
        f"Val RMSE: {val_rmse:.4f} h"
    )

    # Save best model
    if val_mae < best_val_mae:

        best_val_mae = val_mae

        torch.save(
            model.state_dict(),
            "rul_model.pt"
        )

        print(
            "  → Best model saved"
        )


# ============================================================
# TEST
# ============================================================

print("\n============================================")
print("             TEST RESULTS")
print("============================================")

model.load_state_dict(
    torch.load(
        "rul_model.pt",
        map_location=DEVICE
    )
)

test_loss, test_mae, test_rmse = evaluate(
    model,
    test_loader
)

print(
    f"Test Loss : {test_loss:.5f}"
)

print(
    f"Test MAE  : {test_mae:.4f} hours"
)

print(
    f"Test RMSE : {test_rmse:.4f} hours"
)

print("\nModel saved as:")
print("rul_model.pt")

print("\nScaler saved as:")
print("rul_scaler.pkl")