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
    echo "demo QC for ${file.baseName}" > qc/${file.baseName}/qc.txt
    """
}
