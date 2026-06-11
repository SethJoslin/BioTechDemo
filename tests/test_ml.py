"""
Tests for ML models and inference.
"""
import numpy as np
import pytest
import torch


class TestContrastiveEncoder:
    """Tests for the ContrastiveEncoder model."""

    def test_encoder_output_shape(self):
        """Encoder should produce correct output dimensions."""
        from openbioops.models.contrastive import ContrastiveEncoder

        batch_size = 32
        input_dim = 50
        emb_dim = 64

        model = ContrastiveEncoder(input_dim=input_dim, hidden=256, emb_dim=emb_dim)
        x = torch.randn(batch_size, input_dim)

        output = model(x)

        assert output.shape == (batch_size, emb_dim)

    def test_encoder_deterministic_in_eval_mode(self):
        """Encoder should be deterministic in eval mode."""
        from openbioops.models.contrastive import ContrastiveEncoder

        model = ContrastiveEncoder(input_dim=50, hidden=256, emb_dim=64)
        model.eval()

        x = torch.randn(10, 50)

        with torch.no_grad():
            out1 = model(x)
            out2 = model(x)

        assert torch.allclose(out1, out2)

    def test_encoder_different_hidden_sizes(self):
        """Encoder should work with various hidden layer sizes."""
        from openbioops.models.contrastive import ContrastiveEncoder

        for hidden in [64, 128, 512]:
            model = ContrastiveEncoder(input_dim=50, hidden=hidden, emb_dim=64)
            x = torch.randn(8, 50)
            output = model(x)
            assert output.shape == (8, 64)


class TestNTXentLoss:
    """Tests for the NT-Xent contrastive loss."""

    def test_loss_returns_scalar(self):
        """Loss should return a scalar tensor."""
        from openbioops.models.contrastive import nt_xent_loss

        z1 = torch.randn(16, 64)
        z2 = torch.randn(16, 64)

        loss = nt_xent_loss(z1, z2)

        assert loss.ndim == 0  # Scalar
        assert loss.item() > 0  # Loss should be positive

    def test_loss_with_identical_inputs(self):
        """Loss should be lower when z1 and z2 are identical."""
        from openbioops.models.contrastive import nt_xent_loss

        z = torch.randn(16, 64)

        loss_identical = nt_xent_loss(z, z)
        loss_different = nt_xent_loss(z, torch.randn(16, 64))

        # Identical pairs should have lower loss
        assert loss_identical < loss_different

    def test_loss_temperature_scaling(self):
        """Lower temperature should produce higher loss values."""
        from openbioops.models.contrastive import nt_xent_loss

        z1 = torch.randn(16, 64)
        z2 = torch.randn(16, 64)

        loss_low_temp = nt_xent_loss(z1, z2, temperature=0.05)
        loss_high_temp = nt_xent_loss(z1, z2, temperature=0.5)

        # Lower temperature = sharper distribution = typically higher loss
        assert loss_low_temp != loss_high_temp


class TestGetDimsFromCheckpoint:
    """Tests for extracting model dimensions from checkpoint."""

    def test_extract_dims_from_state_dict(self):
        """Should correctly extract dimensions from state dict."""
        from openbioops.models.contrastive import ContrastiveEncoder, get_dims_from_checkpoint

        # Create model and get its state dict
        model = ContrastiveEncoder(input_dim=50, hidden=128, emb_dim=32)
        state_dict = model.state_dict()

        # Extract dimensions
        input_dim, hidden_dim, emb_dim = get_dims_from_checkpoint(state_dict)

        assert input_dim == 50
        assert hidden_dim == 128
        assert emb_dim == 32


class TestFeatureGeneration:
    """Tests for feature extraction pipeline."""

    @pytest.fixture
    def sample_anndata(self, tmp_path):
        """Create a sample AnnData object for testing."""
        import pandas as pd
        import scanpy as sc

        # Create synthetic count matrix (cells x genes)
        np.random.seed(42)
        n_cells, n_genes = 100, 500
        counts = np.random.poisson(5, (n_cells, n_genes)).astype(np.float32)

        # Create AnnData
        adata = sc.AnnData(counts)
        adata.var_names = [f"gene_{i}" for i in range(n_genes)]
        adata.obs_names = [f"cell_{i}" for i in range(n_cells)]

        # Save to file
        h5ad_path = tmp_path / "test_data.h5ad"
        adata.write_h5ad(h5ad_path)

        return h5ad_path

    def test_generate_features_creates_parquet(self, sample_anndata, tmp_path):
        """Feature generation should create a parquet file."""
        from openbioops.processing.features import generate_features

        output_path = tmp_path / "features.parquet"
        generate_features(sample_anndata, output_path, n_pcs=20)

        assert output_path.exists()

    def test_generate_features_output_shape(self, sample_anndata, tmp_path):
        """Output should have correct dimensions."""
        import pandas as pd

        from openbioops.processing.features import generate_features

        output_path = tmp_path / "features.parquet"
        n_pcs = 20
        generate_features(sample_anndata, output_path, n_pcs=n_pcs)

        df = pd.read_parquet(output_path)

        # Should have n_pcs columns
        assert df.shape[1] == n_pcs
        # Column names should be PC0, PC1, ...
        assert list(df.columns) == [f"PC{i}" for i in range(n_pcs)]

    def test_generate_features_from_csv(self, tmp_path):
        """Should handle CSV input."""
        import pandas as pd

        from openbioops.processing.features import generate_features

        # Create CSV count matrix
        np.random.seed(42)
        n_cells, n_genes = 50, 200
        counts = np.random.poisson(5, (n_cells, n_genes))
        df = pd.DataFrame(
            counts,
            index=[f"cell_{i}" for i in range(n_cells)],
            columns=[f"gene_{i}" for i in range(n_genes)],
        )
        csv_path = tmp_path / "counts.csv"
        df.to_csv(csv_path)

        output_path = tmp_path / "features.parquet"
        generate_features(csv_path, output_path, n_pcs=10)

        assert output_path.exists()
        result = pd.read_parquet(output_path)
        assert result.shape[1] == 10


class TestModelServer:
    """Tests for the ModelServer inference wrapper."""

    @pytest.fixture
    def mock_checkpoint(self, tmp_path):
        """Create a mock model checkpoint."""
        from openbioops.models.contrastive import ContrastiveEncoder

        model = ContrastiveEncoder(input_dim=50, hidden=256, emb_dim=64)
        checkpoint_path = tmp_path / "model.pt"
        torch.save(model.state_dict(), checkpoint_path)
        return checkpoint_path

    def test_model_server_loads_checkpoint(self, mock_checkpoint):
        """ModelServer should load checkpoint correctly."""
        from app.ml.model_server import ModelServer

        server = ModelServer(checkpoint=mock_checkpoint)

        assert server.input_dim == 50
        assert server.emb_dim == 64

    def test_model_server_embed(self, mock_checkpoint, tmp_path):
        """ModelServer.embed should produce embeddings."""
        import pandas as pd

        from app.ml.model_server import ModelServer

        # Create feature parquet
        np.random.seed(42)
        features = pd.DataFrame(
            np.random.randn(100, 50),
            columns=[f"PC{i}" for i in range(50)],
        )
        feature_path = tmp_path / "features.parquet"
        features.to_parquet(feature_path)

        # Run inference
        server = ModelServer(checkpoint=mock_checkpoint)
        embeddings = server.embed(feature_path)

        assert embeddings.shape == (100, 64)
        assert list(embeddings.columns) == [f"emb_{i}" for i in range(64)]
