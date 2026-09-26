import torch
import torch.nn as nn


class GRURULRegressor(nn.Module):

    def __init__(
        self,
        n_features=8,
        hidden=96,
        layers=2,
        dropout=0.15
    ):
        super().__init__()

        self.gru = nn.GRU(
            input_size=n_features,
            hidden_size=hidden,
            num_layers=layers,
            batch_first=True,
            dropout=dropout if layers > 1 else 0.0
        )

        self.norm = nn.LayerNorm(hidden)

        self.fc1 = nn.Linear(hidden, 64)

        self.activation = nn.GELU()

        self.dropout = nn.Dropout(dropout)

        self.fc2 = nn.Linear(64, 1)

        self.output_activation = nn.Softplus()

    def forward(self, x):

        # x:
        # (batch, sequence_length, features)

        output, _ = self.gru(x)

        # Last timestep
        x = output[:, -1, :]

        x = self.norm(x)

        x = self.fc1(x)

        x = self.activation(x)

        x = self.dropout(x)

        x = self.fc2(x)

        # RUL must be >= 0
        x = self.output_activation(x)

        return x.squeeze(1)