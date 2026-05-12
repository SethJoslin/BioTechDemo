#!/usr/bin/env python3
"""
qc_metrics.py — per-cell QC for scRNA-seq count matrices.

Computes:
  - n_genes_by_counts   : genes detected per cell
  - total_counts        : UMI counts per cell
  - pct_counts_mt       : mitochondrial gene percentage
  - doublet_score       : scrublet doublet score (if scrublet installed)

Outputs:
  <out_dir>/cell_qc.parquet   — per-cell metrics
  <out_dir>/qc_summary.json   — dataset-level summary
"""
import argparse
import json
from pathlib import Path

import pandas as pd
import scanpy as sc


def compute_qc(counts_path: str, out_dir: str) -> dict:
    Path(out_dir).mkdir(parents=True, exist_ok=True)

    try:
        df = pd.read_parquet(counts_path)
    except Exception:
        df = pd.read_csv(counts_path, index_col=0)

    ad = sc.AnnData(df)

    # Identify mitochondrial genes (human MT- or mouse mt-)
    ad.var["mt"] = ad.var_names.str.startswith(("MT-", "mt-"))
    sc.pp.calculate_qc_metrics(
        ad, qc_vars=["mt"], percent_top=None, log1p=False, inplace=True
    )

    qc_cols = ["n_genes_by_counts", "total_counts", "pct_counts_mt"]
    cell_qc = ad.obs[qc_cols].copy()

    # Doublet detection — graceful fallback if scrublet not installed
    n_doublets = None
    try:
        import scrublet as scr
        scrub = scr.Scrublet(ad.X, expected_doublet_rate=0.06)
        scores, predicted = scrub.scrub_doublets(verbose=False)
        cell_qc["doublet_score"] = scores
        cell_qc["predicted_doublet"] = predicted
        n_doublets = int(predicted.sum())
    except ImportError:
        print("scrublet not installed — skipping doublet detection")

    cell_qc.to_parquet(f"{out_dir}/cell_qc.parquet")

    summary = {
        "n_cells": int(ad.n_obs),
        "n_genes": int(ad.n_vars),
        "n_mt_genes": int(ad.var["mt"].sum()),
        "median_genes_per_cell": round(float(cell_qc["n_genes_by_counts"].median()), 1),
        "median_counts_per_cell": round(float(cell_qc["total_counts"].median()), 1),
        "median_pct_mt": round(float(cell_qc["pct_counts_mt"].median()), 3),
        "cells_high_mt_pct": int((cell_qc["pct_counts_mt"] > 20).sum()),
        "cells_low_genes": int((cell_qc["n_genes_by_counts"] < 200).sum()),
        "qc_status": "pass",
    }

    if n_doublets is not None:
        pct = round(n_doublets / ad.n_obs * 100, 1)
        summary["n_predicted_doublets"] = n_doublets
        summary["pct_predicted_doublets"] = pct
        if pct > 15:
            summary["qc_status"] = "warn"

    # Flag low-quality datasets
    if summary["median_genes_per_cell"] < 200 or summary["median_pct_mt"] > 25:
        summary["qc_status"] = "fail"

    with open(f"{out_dir}/qc_summary.json", "w") as f:
        json.dump(summary, f, indent=2)

    print(f"QC complete: {summary['n_cells']} cells x {summary['n_genes']} genes")
    print(f"  Median genes/cell : {summary['median_genes_per_cell']}")
    print(f"  Median counts/cell: {summary['median_counts_per_cell']}")
    print(f"  Median MT%%        : {summary['median_pct_mt']}%%")
    if n_doublets is not None:
        print(f"  Predicted doublets: {n_doublets} ({summary['pct_predicted_doublets']}%%)")
    print(f"  QC status         : {summary['qc_status']}")

    return summary


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--counts", required=True, help="Counts parquet or CSV")
    p.add_argument("--out-dir", required=True, help="Output directory")
    args = p.parse_args()
    compute_qc(args.counts, args.out_dir)
