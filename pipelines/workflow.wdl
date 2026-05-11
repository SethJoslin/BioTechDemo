version 1.0

# OpenBioOps — WDL equivalent of the Nextflow pipeline
# Runs QC → quantification → feature extraction

workflow OpenBioOps {
  input {
    Array[File] input_files
    Int n_top_genes = 2000
  }

  scatter (f in input_files) {
    call QC { input: sample_file = f }
    call Quantify { input: sample_file = f }
    call ExtractFeatures {
      input:
        counts_file = Quantify.counts,
        n_top_genes = n_top_genes
    }
  }

  output {
    Array[File] qc_reports   = QC.report
    Array[File] counts       = Quantify.counts
    Array[File] features     = ExtractFeatures.features
  }
}

task QC {
  input { File sample_file }
  command <<<
    mkdir -p qc
    echo "QC for ~{basename(sample_file)}" > qc/report.txt
  >>>
  output { File report = "qc/report.txt" }
  runtime { docker: "python:3.11-slim" memory: "2 GB" cpu: 1 }
}

task Quantify {
  input { File sample_file }
  command <<<
    python3 -c "
import pandas as pd
df = pd.DataFrame([[1,2,3]], columns=['geneA','geneB','geneC'])
df.to_parquet('counts.parquet')
"
  >>>
  output { File counts = "counts.parquet" }
  runtime { docker: "python:3.11-slim" memory: "4 GB" cpu: 2 }
}

task ExtractFeatures {
  input { File counts_file  Int n_top_genes }
  command <<<
    python3 /scripts/extract_features.py \
      --counts ~{counts_file} \
      --out features.parquet
  >>>
  output { File features = "features.parquet" }
  runtime { docker: "openbioops/feature-extract:latest" memory: "8 GB" cpu: 4 }
}