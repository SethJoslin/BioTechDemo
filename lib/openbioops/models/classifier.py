"""
Cell type classifier using transfer learning from contrastive encoder.

This module provides a classifier that leverages pre-trained embeddings
for cell type annotation, enabling rapid annotation of new datasets.
"""
from __future__ import annotations
from pathlib import Path
from typing import Optional

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import DataLoader, TensorDataset

from .contrastive import ContrastiveEncoder


class CellTypeClassifier(nn.Module):
    """Cell type classifier using frozen contrastive encoder.

    Uses transfer learning: the encoder is frozen and only the
    classification head is trained on labeled data.

    Args:
        encoder: Pre-trained ContrastiveEncoder
        num_classes: Number of cell types to classify
        dropout: Dropout rate for regularization
    """

    def __init__(
        self,
        encoder: ContrastiveEncoder,
        num_classes: int,
        dropout: float = 0.3,
    ):
        super().__init__()
        self.encoder = encoder
        self.num_classes = num_classes

        # Freeze encoder weights
        for param in self.encoder.parameters():
            param.requires_grad = False

        # Classification head
        self.classifier = nn.Sequential(
            nn.Dropout(dropout),
            nn.Linear(encoder.emb_dim, 128),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(128, num_classes),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Forward pass.

        Args:
            x: Input features [batch_size, input_dim]

        Returns:
            Logits [batch_size, num_classes]
        """
        with torch.no_grad():
            embeddings = self.encoder(x)
        return self.classifier(embeddings)

    def predict(self, x: torch.Tensor) -> torch.Tensor:
        """Predict class labels.

        Args:
            x: Input features [batch_size, input_dim]

        Returns:
            Predicted class indices [batch_size]
        """
        logits = self.forward(x)
        return torch.argmax(logits, dim=1)

    def predict_proba(self, x: torch.Tensor) -> torch.Tensor:
        """Predict class probabilities.

        Args:
            x: Input features [batch_size, input_dim]

        Returns:
            Class probabilities [batch_size, num_classes]
        """
        logits = self.forward(x)
        return F.softmax(logits, dim=1)

    def unfreeze_encoder(self, num_layers: int = 1) -> None:
        """Unfreeze top layers of encoder for fine-tuning.

        Args:
            num_layers: Number of encoder layers to unfreeze (from top)
        """
        # Get all parameter groups
        params = list(self.encoder.parameters())
        # Unfreeze last n layers (2 params per layer: weight + bias)
        for param in params[-(num_layers * 2):]:
            param.requires_grad = True


class CellTypeTrainer:
    """Trainer for cell type classifier.

    Handles training loop, validation, and early stopping.
    """

    def __init__(
        self,
        model: CellTypeClassifier,
        learning_rate: float = 1e-3,
        weight_decay: float = 1e-4,
        device: str = "cpu",
    ):
        self.model = model.to(device)
        self.device = device
        self.optimizer = torch.optim.AdamW(
            filter(lambda p: p.requires_grad, model.parameters()),
            lr=learning_rate,
            weight_decay=weight_decay,
        )
        self.criterion = nn.CrossEntropyLoss()
        self.history: dict[str, list[float]] = {"train_loss": [], "val_loss": [], "val_acc": []}

    def fit(
        self,
        X_train: np.ndarray,
        y_train: np.ndarray,
        X_val: Optional[np.ndarray] = None,
        y_val: Optional[np.ndarray] = None,
        epochs: int = 50,
        batch_size: int = 256,
        patience: int = 10,
    ) -> dict[str, list[float]]:
        """Train the classifier.

        Args:
            X_train: Training features [n_samples, n_features]
            y_train: Training labels [n_samples]
            X_val: Validation features (optional)
            y_val: Validation labels (optional)
            epochs: Maximum training epochs
            batch_size: Batch size
            patience: Early stopping patience

        Returns:
            Training history dictionary
        """
        train_dataset = TensorDataset(
            torch.tensor(X_train, dtype=torch.float32),
            torch.tensor(y_train, dtype=torch.long),
        )
        train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True)

        val_loader = None
        if X_val is not None and y_val is not None:
            val_dataset = TensorDataset(
                torch.tensor(X_val, dtype=torch.float32),
                torch.tensor(y_val, dtype=torch.long),
            )
            val_loader = DataLoader(val_dataset, batch_size=batch_size)

        best_val_loss = float("inf")
        patience_counter = 0

        for epoch in range(epochs):
            # Training
            self.model.train()
            train_loss = 0.0
            for X_batch, y_batch in train_loader:
                X_batch = X_batch.to(self.device)
                y_batch = y_batch.to(self.device)

                self.optimizer.zero_grad()
                logits = self.model(X_batch)
                loss = self.criterion(logits, y_batch)
                loss.backward()
                self.optimizer.step()
                train_loss += loss.item()

            train_loss /= len(train_loader)
            self.history["train_loss"].append(train_loss)

            # Validation
            if val_loader:
                val_loss, val_acc = self._validate(val_loader)
                self.history["val_loss"].append(val_loss)
                self.history["val_acc"].append(val_acc)

                # Early stopping
                if val_loss < best_val_loss:
                    best_val_loss = val_loss
                    patience_counter = 0
                else:
                    patience_counter += 1
                    if patience_counter >= patience:
                        print(f"Early stopping at epoch {epoch + 1}")
                        break

        return self.history

    def _validate(self, val_loader: DataLoader) -> tuple[float, float]:
        """Run validation."""
        self.model.eval()
        val_loss = 0.0
        correct = 0
        total = 0

        with torch.no_grad():
            for X_batch, y_batch in val_loader:
                X_batch = X_batch.to(self.device)
                y_batch = y_batch.to(self.device)

                logits = self.model(X_batch)
                loss = self.criterion(logits, y_batch)
                val_loss += loss.item()

                preds = torch.argmax(logits, dim=1)
                correct += (preds == y_batch).sum().item()
                total += y_batch.size(0)

        return val_loss / len(val_loader), correct / total

    def save(self, path: Path) -> None:
        """Save model checkpoint."""
        torch.save({
            "model_state_dict": self.model.state_dict(),
            "num_classes": self.model.num_classes,
            "history": self.history,
        }, path)

    @classmethod
    def load(
        cls,
        path: Path,
        encoder: ContrastiveEncoder,
        device: str = "cpu",
    ) -> "CellTypeTrainer":
        """Load model from checkpoint."""
        checkpoint = torch.load(path, map_location=device)
        model = CellTypeClassifier(encoder, checkpoint["num_classes"])
        model.load_state_dict(checkpoint["model_state_dict"])
        trainer = cls(model, device=device)
        trainer.history = checkpoint["history"]
        return trainer
