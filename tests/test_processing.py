import tempfile
from pathlib import Path
import pandas as pd
import numpy as np
from openbioops.processing.features import generate_features

def test_generate_features_parquet(tmp_path):
    raw = tmp_path / "raw.parquet"
    df = pd.DataFrame(np.random.poisson(2, (100, 500)), columns=[f"g{i}" for i in range(500)])
    df.to_parquet(raw)
    out = tmp_path / "features.parquet"
    generate_features(str(raw), out, n_pcs=10)
    assert out.exists()
    result = pd.read_parquet(out)
    assert result.shape == (100, 10)
