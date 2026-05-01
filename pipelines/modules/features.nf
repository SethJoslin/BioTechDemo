nextflow.enable.dsl=2

process extract_features {
  tag { counts.baseName }
  input:
    path counts
  output:
    path "features/${counts.baseName}.parquet"
  script:
    """
    mkdir -p features
    python - <<'PY'
import pandas as pd
import sys
p = sys.argv[1]
df = pd.read_parquet(p)
# minimal transform: add a column and write out
df['sum'] = df.sum(axis=1)
df.to_parquet('features/' + p.split('/')[-1])
PY
    """
}
