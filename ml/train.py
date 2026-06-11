"""
Train a contrastive encoder for scRNA-seq embeddings.

Usage:
    pip install -e ../lib  # Install openbioops package first
    python train.py --input features.parquet --out model.pt
"""
import argparse
from pathlib import Path

import mlflow
import pandas as pd
import torch
from torch.utils.data import DataLoader, Dataset

from openbioops.models.contrastive import ContrastiveEncoder, nt_xent_loss
from mlflow_config import MLflowConfig, log_metrics_step

class TabularDataset(Dataset):
    def __init__(self, df: pd.DataFrame):
        self.X = torch.tensor(df.values.astype("float32"))

    def __len__(self):
        return len(self.X)

    def __getitem__(self, idx):
        return self.X[idx]


def augment(x: torch.Tensor, dropout_rate: float = 0.1) -> torch.Tensor:
    """Simulate scRNA-seq dropout by randomly zeroing features."""
    mask = torch.bernoulli(torch.ones_like(x) * (1 - dropout_rate))
    return x * mask


def train(args):
    # Initialize MLflow configuration
    mlflow_config = MLflowConfig(experiment_name="openbioops-contrastive")

    df = pd.read_parquet(args.input)
    ds = TabularDataset(df)
    dl = DataLoader(ds, batch_size=args.batch_size, shuffle=True, drop_last=True)

    encoder = ContrastiveEncoder(input_dim=df.shape[1], hidden=256, emb_dim=64)
    opt = torch.optim.Adam(encoder.parameters(), lr=args.lr)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=args.epochs)

    with mlflow.start_run():
        # Log hyperparameters
        mlflow.log_params({
            "epochs": args.epochs,
            "batch_size": args.batch_size,
            "lr": args.lr,
            "temperature": args.temperature,
            "input_dim": df.shape[1],
            "hidden_dim": 256,
            "emb_dim": 64,
            "optimizer": "Adam",
            "scheduler": "CosineAnnealing",
        })

        # Log tags for filtering
        mlflow.set_tags({
            "model_type": "contrastive_encoder",
            "data_type": "scRNA-seq",
            "framework": "pytorch",
        })

        best_loss = float('inf')
        for epoch in range(1, args.epochs + 1):
            encoder.train()
            epoch_loss = 0.0
            batch_count = 0

            for x in dl:
                z1 = encoder(augment(x, dropout_rate=0.1))
                z2 = encoder(augment(x, dropout_rate=0.1))
                loss = nt_xent_loss(z1, z2, temperature=args.temperature)
                opt.zero_grad()
                loss.backward()
                opt.step()
                epoch_loss += loss.item()
                batch_count += 1

            scheduler.step()
            avg_loss = epoch_loss / batch_count
            current_lr = scheduler.get_last_lr()[0]

            # Log metrics for this epoch
            log_metrics_step({
                "train_loss": avg_loss,
                "learning_rate": current_lr,
            }, step=epoch)

            # Track best model
            if avg_loss < best_loss:
                best_loss = avg_loss
                mlflow.log_metric("best_loss", best_loss)

            print(f"Epoch {epoch:>3}/{args.epochs}  loss={avg_loss:.4f}  lr={current_lr:.6f}")

        # Save and log final model
        torch.save(encoder.state_dict(), args.out)

        # Log model to MLflow with registry
        mlflow.pytorch.log_model(
            encoder,
            "model",
            registered_model_name="contrastive_encoder",
        )

        # Log model artifact
        mlflow.log_artifact(args.out, artifact_path="checkpoints")

        # Log final metrics summary
        mlflow.log_metrics({
            "final_loss": avg_loss,
            "best_loss": best_loss,
            "total_batches": epoch * batch_count,
        })

        print(f"/nTraining complete!")
        print(f"Best loss: {best_loss:.4f}")
        print(f"Model saved -> {args.out}")
        print(f"MLflow run: {mlflow.active_run().info.run_id}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--epochs", type=int, default=20)
    parser.add_argument("--batch-size", type=int, default=256)
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--temperature", type=float, default=0.1)
    args = parser.parse_args()
    train(args)
