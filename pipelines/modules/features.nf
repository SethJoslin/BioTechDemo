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
    python - "${counts}" <<'PY'
import sys, pandas as pd

input_path = sys.argv[1]
try:
    df = pd.read_parquet(input_path)
except Exception:
    df = pd.read_csv(input_path, index_col=0)

df['sum'] = df.sum(axis=1)
out = 'features/' + input_path.split('/')[-1]
if not out.endswith('.parquet'):
    out = out.rsplit('.', 1)[0] + '.parquet'
df.to_parquet(out)
PY
    """
}