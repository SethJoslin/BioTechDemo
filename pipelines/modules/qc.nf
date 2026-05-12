nextflow.enable.dsl=2

process fastqc {
  tag { file.baseName }
  input:
    path file
  output:
    path "qc/${file.baseName}"
  script:
    """
    mkdir -p qc/${file.baseName}
    python - <<'PY'
import sys, json
sys.path.insert(0, '${projectDir}/containers/qc')
from qc_metrics import compute_qc

summary = compute_qc('${file}', 'qc/${file.baseName}')
PY
    """
}
