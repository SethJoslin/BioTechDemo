nextflow.enable.dsl=2

process quantify {
  tag { file.baseName }
  input:
    path file
  output:
    path "counts/${file.baseName}.parquet"
  script:
    """
    mkdir -p counts
    python - <<'PY'
import pandas as pd
# create a tiny fake counts table for demo
df = pd.DataFrame([[1,2,3]], columns=['geneA','geneB','geneC'])
df.to_parquet('counts/${file.baseName}.parquet')
PY
    """
}
