"""
Unit tests for staged pipeline functions.

Tests core pipeline logic without Prefect or Docker dependencies.
"""
import pytest
import tempfile
import logging
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import numpy as np

from lib.openbioops.processing.pipeline import (
    stage_1_qc,
    stage_2_pca,
    stage_3_umap,
    stage_4_clustering,
)


@pytest.fixture
def temp_dir():
    """Create temporary directory for test outputs."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def mock_adata():
    """Create mock AnnData object."""
    mock = MagicMock()
    mock.n_obs = 2700  # Number of cells
    mock.n_vars = 32000  # Number of genes
    mock.obs_names = [f"cell_{i}" for i in range(2700)]
    mock.var_names = [f"gene_{i}" for i in range(32000)]

    # Mock observations DataFrame
    mock.obs = MagicMock()
    mock.obs.copy.return_value = MagicMock()

    # Mock write method
    mock.write = Mock()

    return mock


@pytest.fixture
def mock_logger():
    """Create mock logger."""
    return Mock(spec=logging.Logger)


class TestStage1QC:
    """Tests for Stage 1: QC filtering."""

    @patch('lib.openbioops.processing.pipeline.compute_qc_metrics')
    @patch('lib.openbioops.processing.pipeline.apply_qc_filters')
    @patch('lib.openbioops.processing.pipeline.sc.read_h5ad')
    def test_stage_1_success(
        self,
        mock_read,
        mock_apply_filters,
        mock_compute_qc,
        mock_adata,
        temp_dir,
        mock_logger
    ):
        """Test successful QC stage execution."""
        # Setup mocks
        mock_read.return_value = mock_adata
        mock_compute_qc.return_value = {
            "n_cells": 2700,
            "n_genes": 32000,
            "median_genes_per_cell": 1500,
            "median_counts_per_cell": 4500,
            "median_pct_mt": 3.5,
        }
        mock_filtered = MagicMock()
        mock_filtered.n_obs = 2500  # 200 cells filtered out
        mock_filtered.write = Mock()
        mock_apply_filters.return_value = mock_filtered

        # Execute
        result = stage_1_qc(
            run_id="test_run",
            raw_path="data/test.h5ad",
            output_dir=temp_dir,
            min_genes=200,
            max_genes=5000,
            max_pct_mt=20.0,
            logger=mock_logger
        )

        # Assertions
        assert result["stage"] == 1
        assert result["status"] == "completed"
        assert result["n_cells_out"] == 2500
        assert "checkpoint_path" in result
        assert "duration_sec" in result
        assert "qc_metrics" in result

        # Verify checkpoint was saved
        mock_filtered.write.assert_called_once()

        # Verify logger was used
        assert mock_logger.info.call_count > 0

    @patch('lib.openbioops.processing.pipeline.sc.read_h5ad')
    def test_stage_1_file_not_found(self, mock_read, temp_dir, mock_logger):
        """Test QC stage with missing input file."""
        mock_read.side_effect = FileNotFoundError("File not found")

        with pytest.raises(FileNotFoundError):
            stage_1_qc(
                run_id="test_run",
                raw_path="nonexistent.h5ad",
                output_dir=temp_dir,
                logger=mock_logger
            )

    def test_stage_1_no_logger(self, temp_dir):
        """Test QC stage without logger (should not crash)."""
        with patch('lib.openbioops.processing.pipeline.sc.read_h5ad') as mock_read, \
             patch('lib.openbioops.processing.pipeline.compute_qc_metrics') as mock_qc, \
             patch('lib.openbioops.processing.pipeline.apply_qc_filters') as mock_filter:

            mock_adata = MagicMock()
            mock_adata.n_obs = 2700
            mock_read.return_value = mock_adata
            mock_qc.return_value = {"n_cells": 2700}
            mock_filtered = MagicMock()
            mock_filtered.n_obs = 2500
            mock_filtered.write = Mock()
            mock_filter.return_value = mock_filtered

            # Should not raise error even without logger
            result = stage_1_qc(
                run_id="test_run",
                raw_path="data/test.h5ad",
                output_dir=temp_dir,
                logger=None  # No logger
            )

            assert result["status"] == "completed"


class TestStage2PCA:
    """Tests for Stage 2: PCA dimensionality reduction."""

    @patch('lib.openbioops.processing.pipeline.generate_features')
    @patch('lib.openbioops.processing.pipeline.sc.pp.highly_variable_genes')
    @patch('lib.openbioops.processing.pipeline.sc.pp.normalize_total')
    @patch('lib.openbioops.processing.pipeline.sc.pp.log1p')
    @patch('lib.openbioops.processing.pipeline.sc.tl.pca')
    @patch('lib.openbioops.processing.pipeline.sc.read_h5ad')
    def test_stage_2_success(
        self,
        mock_read,
        mock_pca,
        mock_log1p,
        mock_normalize,
        mock_hvg,
        mock_generate_features,
        mock_adata,
        temp_dir,
        mock_logger
    ):
        """Test successful PCA stage execution."""
        # Setup mock
        mock_read.return_value = mock_adata
        mock_adata.obsm = {"X_pca": np.random.randn(2700, 50)}

        # Create checkpoint from stage 1
        checkpoint = temp_dir / "test_run_qc.h5ad"
        checkpoint.touch()

        # Execute
        result = stage_2_pca(
            run_id="test_run",
            qc_checkpoint=checkpoint,
            output_dir=temp_dir,
            features_dir=temp_dir,
            n_hvg=2000,
            n_pcs=50,
            logger=mock_logger
        )

        # Assertions
        assert result["stage"] == 2
        assert result["status"] == "completed"
        assert result["n_pcs"] == 50
        assert "checkpoint_path" in result
        assert "duration_sec" in result

        # Verify PCA was computed
        mock_pca.assert_called_once()
        mock_adata.write.assert_called_once()

        # Verify feature vector generation
        mock_generate_features.assert_called_once()

    def test_stage_2_checkpoint_not_found(self, temp_dir, mock_logger):
        """Test PCA stage with missing checkpoint."""
        nonexistent = temp_dir / "nonexistent.h5ad"

        with pytest.raises(FileNotFoundError):
            stage_2_pca(
                run_id="test_run",
                qc_checkpoint=nonexistent,
                output_dir=temp_dir,
                features_dir=temp_dir,
                logger=mock_logger
            )


class TestStage3UMAP:
    """Tests for Stage 3: UMAP embedding."""

    @patch('lib.openbioops.processing.pipeline.sc.pp.neighbors')
    @patch('lib.openbioops.processing.pipeline.sc.tl.umap')
    @patch('lib.openbioops.processing.pipeline.sc.read_h5ad')
    def test_stage_3_success(
        self,
        mock_read,
        mock_umap,
        mock_neighbors,
        mock_adata,
        temp_dir,
        mock_logger
    ):
        """Test successful UMAP stage execution."""
        # Setup mock
        mock_read.return_value = mock_adata
        mock_adata.obsm = {
            "X_pca": np.random.randn(2700, 50),
            "X_umap": np.random.randn(2700, 2)
        }

        # Create checkpoint from stage 2
        checkpoint = temp_dir / "test_run_pca.h5ad"
        checkpoint.touch()

        # Execute
        result = stage_3_umap(
            run_id="test_run",
            pca_checkpoint=checkpoint,
            output_dir=temp_dir,
            n_neighbors=15,
            min_dist=0.1,
            logger=mock_logger
        )

        # Assertions
        assert result["stage"] == 3
        assert result["status"] == "completed"
        assert result["n_neighbors"] == 15
        assert result["min_dist"] == 0.1
        assert "checkpoint_path" in result
        assert "duration_sec" in result

        # Verify UMAP was computed
        mock_neighbors.assert_called_once_with(mock_adata, n_neighbors=15)
        mock_umap.assert_called_once_with(mock_adata, min_dist=0.1)
        mock_adata.write.assert_called_once()

    def test_stage_3_parameter_validation(self, temp_dir):
        """Test UMAP stage with invalid parameters."""
        checkpoint = temp_dir / "test_run_pca.h5ad"
        checkpoint.touch()

        # n_neighbors too low should raise error or be clamped
        with patch('lib.openbioops.processing.pipeline.sc.read_h5ad'):
            # This should raise ValueError or be handled gracefully
            with pytest.raises((ValueError, TypeError)):
                stage_3_umap(
                    run_id="test_run",
                    pca_checkpoint=checkpoint,
                    output_dir=temp_dir,
                    n_neighbors=1,  # Invalid: too low
                    logger=None
                )


class TestStage4Clustering:
    """Tests for Stage 4: Leiden clustering."""

    @patch('lib.openbioops.processing.pipeline.sc.tl.leiden')
    @patch('lib.openbioops.processing.pipeline.sc.read_h5ad')
    def test_stage_4_success(
        self,
        mock_read,
        mock_leiden,
        mock_adata,
        temp_dir,
        mock_logger
    ):
        """Test successful clustering stage execution."""
        # Setup mock
        mock_read.return_value = mock_adata
        mock_adata.obs = {"leiden": ["0", "1", "2"] * 900}  # 3 clusters

        # Create checkpoint from stage 3
        checkpoint = temp_dir / "test_run_umap.h5ad"
        checkpoint.touch()

        # Execute
        result = stage_4_clustering(
            run_id="test_run",
            umap_checkpoint=checkpoint,
            output_dir=temp_dir,
            resolution=1.0,
            logger=mock_logger
        )

        # Assertions
        assert result["stage"] == 4
        assert result["status"] == "completed"
        assert result["resolution"] == 1.0
        assert result["n_clusters"] == 3
        assert "checkpoint_path" in result
        assert "duration_sec" in result

        # Verify clustering was computed
        mock_leiden.assert_called_once_with(mock_adata, resolution=1.0)
        mock_adata.write.assert_called_once()

    @patch('lib.openbioops.processing.pipeline.sc.tl.leiden')
    @patch('lib.openbioops.processing.pipeline.sc.read_h5ad')
    def test_stage_4_resolution_range(
        self,
        mock_read,
        mock_leiden,
        mock_adata,
        temp_dir
    ):
        """Test clustering with different resolution values."""
        mock_read.return_value = mock_adata
        checkpoint = temp_dir / "test_run_umap.h5ad"
        checkpoint.touch()

        # Low resolution -> fewer clusters
        mock_adata.obs = {"leiden": ["0", "1"] * 1350}
        result_low = stage_4_clustering(
            run_id="test_run",
            umap_checkpoint=checkpoint,
            output_dir=temp_dir,
            resolution=0.5,
            logger=None
        )
        assert result_low["n_clusters"] == 2

        # High resolution -> more clusters
        mock_adata.obs = {"leiden": [str(i % 10) for i in range(2700)]}
        result_high = stage_4_clustering(
            run_id="test_run",
            umap_checkpoint=checkpoint,
            output_dir=temp_dir,
            resolution=2.0,
            logger=None
        )
        assert result_high["n_clusters"] == 10


class TestPipelineIntegration:
    """Integration tests for full pipeline flow."""

    def test_checkpoint_chain(self, temp_dir):
        """Test that each stage produces checkpoint for next stage."""
        with patch('lib.openbioops.processing.pipeline.sc.read_h5ad') as mock_read, \
             patch('lib.openbioops.processing.pipeline.compute_qc_metrics'), \
             patch('lib.openbioops.processing.pipeline.apply_qc_filters') as mock_filter, \
             patch('lib.openbioops.processing.pipeline.generate_features'), \
             patch('lib.openbioops.processing.pipeline.sc.pp.normalize_total'), \
             patch('lib.openbioops.processing.pipeline.sc.pp.log1p'), \
             patch('lib.openbioops.processing.pipeline.sc.pp.highly_variable_genes'), \
             patch('lib.openbioops.processing.pipeline.sc.tl.pca'), \
             patch('lib.openbioops.processing.pipeline.sc.pp.neighbors'), \
             patch('lib.openbioops.processing.pipeline.sc.tl.umap'), \
             patch('lib.openbioops.processing.pipeline.sc.tl.leiden'):

            mock_adata = MagicMock()
            mock_adata.n_obs = 2700
            mock_adata.obsm = {
                "X_pca": np.random.randn(2700, 50),
                "X_umap": np.random.randn(2700, 2)
            }
            mock_adata.obs = {"leiden": ["0", "1", "2"] * 900}
            mock_adata.write = Mock()

            mock_read.return_value = mock_adata
            mock_filter.return_value = mock_adata

            # Stage 1
            result_1 = stage_1_qc(
                run_id="test_run",
                raw_path="data/test.h5ad",
                output_dir=temp_dir
            )
            checkpoint_1 = Path(result_1["checkpoint_path"])
            assert "qc.h5ad" in str(checkpoint_1)

            # Stage 2 uses stage 1 checkpoint
            result_2 = stage_2_pca(
                run_id="test_run",
                qc_checkpoint=checkpoint_1,
                output_dir=temp_dir,
                features_dir=temp_dir
            )
            checkpoint_2 = Path(result_2["checkpoint_path"])
            assert "pca.h5ad" in str(checkpoint_2)

            # Stage 3 uses stage 2 checkpoint
            result_3 = stage_3_umap(
                run_id="test_run",
                pca_checkpoint=checkpoint_2,
                output_dir=temp_dir
            )
            checkpoint_3 = Path(result_3["checkpoint_path"])
            assert "umap.h5ad" in str(checkpoint_3)

            # Stage 4 uses stage 3 checkpoint
            result_4 = stage_4_clustering(
                run_id="test_run",
                umap_checkpoint=checkpoint_3,
                output_dir=temp_dir
            )
            checkpoint_4 = Path(result_4["checkpoint_path"])
            assert "clustered.h5ad" in str(checkpoint_4)

    def test_all_stages_return_metadata(self):
        """Verify all stages return required metadata fields."""
        required_fields = ["stage", "status", "checkpoint_path", "duration_sec"]

        with patch('lib.openbioops.processing.pipeline.sc.read_h5ad') as mock_read, \
             patch('lib.openbioops.processing.pipeline.compute_qc_metrics') as mock_qc, \
             patch('lib.openbioops.processing.pipeline.apply_qc_filters') as mock_filter:

            mock_adata = MagicMock()
            mock_adata.n_obs = 2700
            mock_adata.write = Mock()
            mock_read.return_value = mock_adata
            mock_qc.return_value = {"n_cells": 2700}
            mock_filter.return_value = mock_adata

            with tempfile.TemporaryDirectory() as tmpdir:
                result = stage_1_qc(
                    run_id="test",
                    raw_path="data/test.h5ad",
                    output_dir=Path(tmpdir)
                )

                for field in required_fields:
                    assert field in result, f"Missing required field: {field}"

                assert result["status"] == "completed"
                assert result["duration_sec"] >= 0


class TestNoPrefectCoupling:
    """Tests to ensure pipeline has no Prefect dependencies."""

    def test_no_prefect_imports(self):
        """Verify pipeline.py does not import Prefect."""
        import lib.openbioops.processing.pipeline as pipeline_module
        import sys

        # Check that prefect is not in the module's dependencies
        module_vars = vars(pipeline_module)
        for name, value in module_vars.items():
            if hasattr(value, '__module__'):
                assert 'prefect' not in value.__module__, \
                    f"Found Prefect dependency: {name} from {value.__module__}"

    def test_functions_accept_standard_logger(self):
        """Verify all stage functions accept standard logging.Logger."""
        import inspect

        for func in [stage_1_qc, stage_2_pca, stage_3_umap, stage_4_clustering]:
            sig = inspect.signature(func)
            assert 'logger' in sig.parameters, f"{func.__name__} missing logger parameter"

            logger_param = sig.parameters['logger']
            # Should be Optional[logging.Logger]
            assert logger_param.default is None, \
                f"{func.__name__} logger should default to None"

    def test_functions_return_plain_dicts(self):
        """Verify stage functions return plain dicts, not Prefect States."""
        with patch('lib.openbioops.processing.pipeline.sc.read_h5ad') as mock_read, \
             patch('lib.openbioops.processing.pipeline.compute_qc_metrics') as mock_qc, \
             patch('lib.openbioops.processing.pipeline.apply_qc_filters') as mock_filter:

            mock_adata = MagicMock()
            mock_adata.n_obs = 2700
            mock_adata.write = Mock()
            mock_read.return_value = mock_adata
            mock_qc.return_value = {"n_cells": 2700}
            mock_filter.return_value = mock_adata

            with tempfile.TemporaryDirectory() as tmpdir:
                result = stage_1_qc(
                    run_id="test",
                    raw_path="data/test.h5ad",
                    output_dir=Path(tmpdir)
                )

                # Should be plain dict
                assert isinstance(result, dict)
                assert type(result).__name__ == 'dict'  # Not a subclass