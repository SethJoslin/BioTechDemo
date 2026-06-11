"""
Generate the initial model checkpoint from PBMC 3k data.

This script:
1. Loads raw PBMC 3k data
2. Extracts PCA features
3. Trains a contrastive encoder
4. Saves model.pt AND registers it in MLflow

Usage:
    python ml/generate_model.py

Or via Make:
    make generate-model
"""
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "lib"))

import mlflow
import pandas as pd
import torch
from openbioops.processing.features import generate_features
from openbioops.models.contrastive import ContrastiveEncoder, nt_xent_loss
from torch.utils.data import DataLoader, Dataset
from ml.mlflow_config import MLflowConfig, log_metrics_step


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


def main():
    print("=" * 70)
    print("  OpenBioOps Model Generation")
    print("=" * 70)

    # Paths
    raw_data = project_root / "data" / "pbmc3k_raw.h5ad"
    features_path = project_root / "artifacts" / "features" / "pbmc3k.parquet"
    model_path = project_root / "ml" / "model.pt"

    # Create directories
    features_path.parent.mkdir(parents=True, exist_ok=True)
    model_path.parent.mkdir(parents=True, exist_ok=True)

    # Step 1: Generate features if they don't exist
    if not features_path.exists():
        print(f"/n[1/3] Extracting PCA features from {raw_data.name}...")
        generate_features(
            raw_path=raw_data,
            output_path=features_path,
            n_pcs=50,
            n_top_genes=2000
        )
        print(f"      ✓ Features saved to {features_path}")
    else:
        print(f"/n[1/3] Features already exist at {features_path}")

    # Step 2: Load features and train model
    print(f"/n[2/3] Training contrastive encoder...")
    df = pd.read_parquet(features_path)
    print(f"      Features shape: {df.shape}")

    # Initialize MLflow
    mlflow_config = MLflowConfig(experiment_name="openbioops-contrastive")

    # Model configuration
    input_dim = df.shape[1]
    hidden_dim = 256
    emb_dim = 64
    epochs = 20
    batch_size = 256
    lr = 1e-3
    temperature = 0.1

    # Create dataset and dataloader
    ds = TabularDataset(df)
    dl = DataLoader(ds, batch_size=batch_size, shuffle=True, drop_last=True)

    # Initialize model
    encoder = ContrastiveEncoder(input_dim=input_dim, hidden=hidden_dim, emb_dim=emb_dim)
    opt = torch.optim.Adam(encoder.parameters(), lr=lr)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=epochs)

    # Start MLflow run
    with mlflow.start_run(run_name="initial_model_v1.0"):
        # Log hyperparameters
        mlflow.log_params({
            "epochs": epochs,
            "batch_size": batch_size,
            "lr": lr,
            "temperature": temperature,
            "input_dim": input_dim,
            "hidden_dim": hidden_dim,
            "emb_dim": emb_dim,
            "optimizer": "Adam",
            "scheduler": "CosineAnnealing",
            "n_samples": len(df),
            "data_source": "pbmc3k_raw.h5ad",
        })

        # Log tags
        mlflow.set_tags({
            "model_type": "contrastive_encoder",
            "data_type": "scRNA-seq",
            "framework": "pytorch",
            "dataset": "pbmc3k",
            "stage": "production",  # Mark as production-ready
        })

        # Training loop
        best_loss = float('inf')
        print(f"      Training for {epochs} epochs...")

        for epoch in range(1, epochs + 1):
            encoder.train()
            epoch_loss = 0.0
            batch_count = 0

            for x in dl:
                z1 = encoder(augment(x, dropout_rate=0.1))
                z2 = encoder(augment(x, dropout_rate=0.1))
                loss = nt_xent_loss(z1, z2, temperature=temperature)
                opt.zero_grad()
                loss.backward()
                opt.step()
                epoch_loss += loss.item()
                batch_count += 1

            scheduler.step()
            avg_loss = epoch_loss / batch_count
            current_lr = scheduler.get_last_lr()[0]

            # Log metrics
            log_metrics_step({
                "train_loss": avg_loss,
                "learning_rate": current_lr,
            }, step=epoch)

            # Track best
            if avg_loss < best_loss:
                best_loss = avg_loss
                mlflow.log_metric("best_loss", best_loss)

            if epoch % 5 == 0 or epoch == epochs:
                print(f"      Epoch {epoch:>3}/{epochs}  loss={avg_loss:.4f}  lr={current_lr:.6f}")

        print(f"      ✓ Training complete! Best loss: {best_loss:.4f}")

        # Step 3: Save and register model
        print(f"/n[3/3] Saving and registering model...")

        # Save checkpoint
        torch.save(encoder.state_dict(), model_path)
        print(f"      ✓ Checkpoint saved to {model_path}")

        # Register model in MLflow
        mlflow.pytorch.log_model(
            encoder,
            "model",
            registered_model_name="contrastive_encoder",
        )

        # Log checkpoint artifact
        mlflow.log_artifact(str(model_path), artifact_path="checkpoints")

        # Log final metrics
        mlflow.log_metrics({
            "final_loss": avg_loss,
            "best_loss": best_loss,
            "total_batches": epoch * batch_count,
        })

        run_id = mlflow.active_run().info.run_id
        print(f"      ✓ Model registered in MLflow")
        print(f"      Run ID: {run_id}")

    print("/n" + "=" * 70)
    print("✓ Model generation complete!")
    print("=" * 70)
    print(f"/nModel checkpoint: {model_path}")
    print(f"MLflow UI: http://localhost:5000")
    print(f"Run ID: {run_id}")
    print("/nTo use this model:")
    print("  1. Start the API: make api")
    print("  2. Model will load automatically from ml/model.pt")
    print("  3. Check /health endpoint to verify model loaded")


if __name__ == "__main__":
    main()
