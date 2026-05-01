#!/usr/bin/env nextflow
nextflow.enable.dsl=2

include { fastqc } from './modules/qc.nf'
include { quantify } from './modules/quant.nf'
include { extract_features } from './modules/features.nf'

workflow {
  // input files (put a tiny demo file in data/)
  Channel.fromPath('data/*').set { reads_ch }

  // run QC and capture its output channel
  def qc_out_ch = reads_ch | fastqc

  // run quantification and capture counts channel (each element is a path)
  def counts_ch = reads_ch | quantify

  // run feature extraction per counts file and capture features channel
  def features_ch = counts_ch | extract_features

  // optional: print counts of produced artifacts
  features_ch.view { "feature artifact: ${it}" }
}
