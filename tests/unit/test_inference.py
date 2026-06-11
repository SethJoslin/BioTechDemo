"""Unit tests for model inference."""
import pytest
import pandas as pd
import torch

from openbioops.models import load_encoder, embed_features


@pytest.mark.unit
@pytest.mark.requires_model
def test_load_encoder(mock_model_checkpoint):
    """Test model loading from checkpoint."""
    model = load_encoder(mock_model_checkpoint)

    # Model should be in eval mode
    assert not model.training

    # Should have expected architecture
    assert hasattr(model, "net")
    assert isinstance(model.net, torch.nn.Sequential)


@pytest.mark.unit
@pytest.mark.requires_model
def test_embed_features(mock_model_checkpoint, sample_parquet):
    """Test embedding generation."""
    model = load_encoder(mock_model_checkpoint)

    # Generate embeddings
    embeddings_df = embed_features(model, sample_parquet, batch_size=32)

    # Check output shape
    assert isinstance(embeddings_df, pd.DataFrame)
    assert len(embeddings_df) == 100  # Same as input
    assert embeddings_df.shape[1] == 64  # Embedding dimension

    # Check column names
    assert all(col.startswith("emb_") for col in embeddings_df.columns)

    # Check index preserved
    assert all(idx.startswith("cell_") for idx in embeddings_df.index)


@pytest.mark.unit
@pytest.mark.requires_model
def test_embed_features_different_batch_sizes(mock_model_checkpoint, sample_parquet):
    """Test that batch size doesn't significantly affect results."""
    model = load_encoder(mock_model_checkpoint)

    # Generate with different batch sizes
    emb1 = embed_features(model, sample_parquet, batch_size=10)
    emb2 = embed_features(model, sample_parquet, batch_size=50)

    # Results should be very similar (allowing for minor numerical differences)
    # Use check_exact=False to allow small floating point differences
    pd.testing.assert_frame_equal(emb1, emb2, atol=1e-5, rtol=1e-5)
