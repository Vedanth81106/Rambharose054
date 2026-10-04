import torch
import torch.nn as nn


class GRURULRegressor(nn.Module):

    def __init__(
        self,
        n_features=35,
        hidden_size=64,
        num_layers=2,
        dropout=0.2
    ):
        super().__init__()

        self.gru = nn.GRU(
            input_size=n_features,
            hidden_size=hidden_size,
            num_layers=num_layers,
            batch_first=True,
            dropout=dropout
        )

        self.layer_norm = nn.LayerNorm(hidden_size)

        self.fc = nn.Sequential(
            nn.Linear(hidden_size, 64),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(64, 1)
        )

    def forward(self, x):

        output, _ = self.gru(x)

        # Last timestep
        x = output[:, -1, :]

        x = self.layer_norm(x)

        x = self.fc(x)

        # RUL normalized to 0-1
        x = torch.sigmoid(x)

        return x.squeeze(-1)