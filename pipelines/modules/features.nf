nextflow.enable.dsl=2
process extract_features {
  tag { counts.baseName }
  container 'openbioops/feature-extract:latest'
  input:
    path counts
  output:
    path "features/${counts.baseName}.parquet"
  script:
    """
    python -c "
from openbioops.processing.features import generate_features
generate_features('${counts}', 'features/${counts.baseName}.parquet')
    "
    """
}
