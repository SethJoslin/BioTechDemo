import argparse

import mlflow
import pandas as pd
import torch
from torch.utils.data import DataLoader, Dataset

from model import ContrastiveEncoder, nt_xent_loss  # noqa: F401


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
    df = pd.read_parquet(args.input)
    ds = TabularDataset(df)
    dl = DataLoader(ds, batch_size=args.batch_size, shuffle=True, drop_last=True)

    encoder = ContrastiveEncoder(input_dim=df.shape[1], hidden=256, emb_dim=64)
    opt = torch.optim.Adam(encoder.parameters(), lr=args.lr)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=args.epochs)

    mlflow.set_experiment("openbioops-contrastive")
    with mlflow.start_run():
        mlflow.log_params({
            "epochs": args.epochs,
            "batch_size": args.batch_size,
            "lr": args.lr,
            "temperature": args.temperature,
            "input_dim": df.shape[1],
        })

        for epoch in range(1, args.epochs + 1):
            encoder.train()
            epoch_loss = 0.0
            for x in dl:
                z1 = encoder(augment(x, dropout_rate=0.1))
                z2 = encoder(augment(x, dropout_rate=0.1))
                loss = nt_xent_loss(z1, z2, temperature=args.temperature)
                opt.zero_grad()
                loss.backward()
                opt.step()
                epoch_loss += loss.item()
            scheduler.step()
            avg = epoch_loss / len(dl)
            print(f"Epoch {epoch:>3}/{args.epochs}  loss={avg:.4f}")
            mlflow.log_metric("train_loss", avg, step=epoch)

        mlflow.log_artifact(args.out, artifact_path="model")

    torch.save(encoder.state_dict(), args.out)
    print(f"Saved model → {args.out}")


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