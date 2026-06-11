import { useState, useEffect } from "react";
import {
  fetchQC,
  fetchSimilarity,
  computeVector,
  startAnalysis,
  getAnalysisStatus,
  rerunStage
} from "../api";
import UMAPViewer from "./UMAPViewer";

// Spinner animation
const spinnerAnimation = `
@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}
`;

const styleSheet = document.createElement("style");
styleSheet.textContent = spinnerAnimation;
if (!document.head.querySelector('style[data-spinner]')) {
  styleSheet.setAttribute('data-spinner', 'true');
  document.head.appendChild(styleSheet);
}

const styles = {
  wrap: { border: "1px solid #e2e8f0", borderRadius: 8, padding: 20 },
  empty: { color: "#a0aec0", fontSize: 14, textAlign: "center", paddingTop: 60 },
  title: { fontSize: 17, fontWeight: 700, marginBottom: 4 },
  id: { fontSize: 12, color: "#718096", marginBottom: 20 },
  section: { marginBottom: 24 },
  sectionTitle: { fontSize: 13, fontWeight: 600, color: "#4a5568",
                  textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 10 },
  grid: { display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 },
  metric: { background: "#f7fafc", borderRadius: 6, padding: "10px 14px" },
  metricLabel: { fontSize: 11, color: "#718096", marginBottom: 2 },
  metricValue: { fontSize: 18, fontWeight: 700, color: "#2d3748" },
  simRow: { display: "flex", justifyContent: "space-between", alignItems: "center",
            padding: "8px 12px", background: "#f7fafc", borderRadius: 6, marginBottom: 6 },
  simId: { fontSize: 13, fontFamily: "monospace" },
  simScore: { fontSize: 13, fontWeight: 600, color: "#3182ce" },
  btn: { padding: "7px 14px", background: "#3182ce", color: "#fff",
         border: "none", borderRadius: 6, fontSize: 13, cursor: "pointer" },
  btnDisabled: { padding: "7px 14px", background: "#a0aec0", color: "#fff",
         border: "none", borderRadius: 6, fontSize: 13, cursor: "not-allowed", opacity: 0.6 },
  btnSecondary: { padding: "7px 14px", background: "#e2e8f0", color: "#2d3748",
         border: "none", borderRadius: 6, fontSize: 13, cursor: "pointer", marginLeft: 8 },
  error: { color: "#e53e3e", fontSize: 13, marginTop: 8 },
  success: { color: "#38a169", fontSize: 13, marginTop: 8 },
  spinner: { display: "inline-block", marginRight: 6, animation: "spin 1s linear infinite" },
  stageRow: { display: "flex", alignItems: "center", padding: "8px 12px",
              background: "#f7fafc", borderRadius: 6, marginBottom: 6 },
  stageIcon: { fontSize: 18, marginRight: 10, minWidth: 24 },
  stageName: { flex: 1, fontSize: 13, fontWeight: 600 },
  stageDuration: { fontSize: 12, color: "#718096" },
  paramInput: { padding: "6px 10px", border: "1px solid #e2e8f0", borderRadius: 4, fontSize: 13, width: "100%" },
  paramLabel: { fontSize: 12, color: "#4a5568", marginBottom: 4, display: "block" },
  paramGrid: { display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10, marginTop: 10 },
  advancedToggle: { fontSize: 12, color: "#3182ce", cursor: "pointer", marginBottom: 10 }
};

function Metric({ label, value }) {
  return (
    <div style={styles.metric}>
      <div style={styles.metricLabel}>{label}</div>
      <div style={styles.metricValue}>{value ?? "—"}</div>
    </div>
  );
}

function StageProgress({ stages }) {
  const getIcon = (status) => {
    if (status === "completed") return "✓";
    if (status === "running") return "⟳";
    if (status === "failed") return "✗";
    return "○";
  };

  const getColor = (status) => {
    if (status === "completed") return "#38a169";
    if (status === "running") return "#3182ce";
    if (status === "failed") return "#e53e3e";
    return "#a0aec0";
  };

  return (
    <div>
      {stages.map(stage => (
        <div key={stage.stage} style={{...styles.stageRow, borderLeft: `4px solid ${getColor(stage.status)}`}}>
          <span style={{...styles.stageIcon, color: getColor(stage.status)}}>
            {stage.status === "running" ? <span style={styles.spinner}>⟳</span> : getIcon(stage.status)}
          </span>
          <span style={styles.stageName}>
            Stage {stage.stage}: {stage.name}
          </span>
          {stage.duration_sec && (
            <span style={styles.stageDuration}>
              {stage.duration_sec}s
            </span>
          )}
        </div>
      ))}
    </div>
  );
}

export default function RunDetail({ token, run }) {
  const [qc, setQC] = useState(null);
  const [sims, setSims] = useState(null);
  const [analysisStatus, setAnalysisStatus] = useState(null);
  const [processing, setProcessing] = useState(false);
  const [error, setError] = useState(null);
  const [successMsg, setSuccessMsg] = useState(null);
  const [rawPath, setRawPath] = useState("/app/data/pbmc3k_raw.h5ad");
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [params, setParams] = useState({
    min_genes: 200,
    max_genes: 5000,
    max_pct_mt: 20,
    n_hvg: 2000,
    n_pcs: 50,
    n_neighbors: 15,
    min_dist: 0.1,
    resolution: 1.0
  });

  // Poll for analysis status
  useEffect(() => {
    if (!run) return;

    let interval;
    const pollStatus = async () => {
      try {
        const status = await getAnalysisStatus(token, run.id);
        setAnalysisStatus(status);

        // Stop polling if complete or failed
        if (status.status === "completed" || status.status === "failed") {
          if (interval) clearInterval(interval);
          // Refresh QC and similarity data
          fetchQC(token, run.id).then(setQC).catch(() => setQC({}));
          fetchSimilarity(token, run.id).then(setSims).catch(() => setSims([]));
        }
      } catch (e) {
        // No workflow yet, that's okay
        setAnalysisStatus(null);
      }
    };

    // Initial fetch
    pollStatus();

    // Poll every 3 seconds if running
    if (analysisStatus && (analysisStatus.status === "pending" || analysisStatus.status === "running")) {
      interval = setInterval(pollStatus, 3000);
    }

    return () => {
      if (interval) clearInterval(interval);
    };
  }, [run, token, analysisStatus?.status]);

  useEffect(() => {
    if (!run) return;
    setQC(null); setSims(null); setError(null);

    fetchQC(token, run.id).then(setQC).catch(() => setQC({}));
    fetchSimilarity(token, run.id).then(setSims).catch(() => setSims([]));
  }, [run, token]);

  async function handleStartAnalysis() {
    setProcessing(true); setError(null); setSuccessMsg(null);
    try {
      await startAnalysis(token, run.id, rawPath, params);
      setSuccessMsg("✓ Analysis started! Stages will execute sequentially.");
      setTimeout(() => setProcessing(false), 2000);
    } catch (e) {
      setError(`Failed to start analysis: ${e.message}`);
      setProcessing(false);
    }
  }

  async function handleRerunStage(stage) {
    setProcessing(true); setError(null); setSuccessMsg(null);
    try {
      await rerunStage(token, run.id, stage, params);
      setSuccessMsg(`✓ Re-ran stage ${stage} with new parameters`);
      setTimeout(() => {
        setProcessing(false);
        // Refresh status
        getAnalysisStatus(token, run.id).then(setAnalysisStatus);
      }, 2000);
    } catch (e) {
      setError(`Failed to re-run stage: ${e.message}`);
      setProcessing(false);
    }
  }

  async function handleComputeVector() {
    setProcessing(true); setError(null);
    try {
      await computeVector(token, run.id);
      const results = await fetchSimilarity(token, run.id);
      setSims(results);
    } catch (e) {
      console.error("Compute vector error:", e);
      setError(`Could not index run: ${e.message}`);
    } finally {
      setProcessing(false);
    }
  }

  if (!run) {
    return <div style={styles.wrap}><div style={styles.empty}>Select a run to view details</div></div>;
  }

  const m = qc?.metrics || {};
  const canRerunUMAP = analysisStatus?.stages?.[1]?.status === "completed";
  const canRerunClustering = analysisStatus?.stages?.[2]?.status === "completed";

  return (
    <div style={styles.wrap}>
      <div style={styles.title}>{run.name}</div>
      <div style={styles.id}>{run.id}</div>

      {/* Analysis Pipeline */}
      <div style={styles.section}>
        <div style={styles.sectionTitle}>Analysis Pipeline</div>
        <p style={{ fontSize: 13, color: "#718096", marginBottom: 10 }}>
          Multi-stage single-cell analysis: QC → PCA → UMAP → Clustering
        </p>

        {analysisStatus ? (
          <>
            <StageProgress stages={analysisStatus.stages} />

            {analysisStatus.error_message && (
              <p style={styles.error}>{analysisStatus.error_message}</p>
            )}

            {/* Parameter tuning after PCA completes */}
            {canRerunUMAP && (
              <div style={{ marginTop: 16, padding: 12, background: "#f0f9ff", borderRadius: 6 }}>
                <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 8 }}>
                  Tune UMAP Parameters
                </div>
                <div style={styles.paramGrid}>
                  <div>
                    <label style={styles.paramLabel}>n_neighbors</label>
                    <input
                      type="number"
                      style={styles.paramInput}
                      value={params.n_neighbors}
                      onChange={(e) => setParams({...params, n_neighbors: parseInt(e.target.value)})}
                    />
                  </div>
                  <div>
                    <label style={styles.paramLabel}>min_dist</label>
                    <input
                      type="number"
                      step="0.1"
                      style={styles.paramInput}
                      value={params.min_dist}
                      onChange={(e) => setParams({...params, min_dist: parseFloat(e.target.value)})}
                    />
                  </div>
                </div>
                <button
                  style={processing ? styles.btnDisabled : styles.btn}
                  onClick={() => handleRerunStage(3)}
                  disabled={processing}
                  title="Re-run UMAP + Clustering with new parameters"
                  style={{ marginTop: 10 }}
                >
                  {processing && <span style={styles.spinner}>⟳</span>}
                  Re-run UMAP
                </button>
              </div>
            )}

            {/* Clustering tuning */}
            {canRerunClustering && (
              <div style={{ marginTop: 16, padding: 12, background: "#f0fff4", borderRadius: 6 }}>
                <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 8 }}>
                  Tune Clustering
                </div>
                <div>
                  <label style={styles.paramLabel}>Resolution (higher = more clusters)</label>
                  <input
                    type="number"
                    step="0.1"
                    style={styles.paramInput}
                    value={params.resolution}
                    onChange={(e) => setParams({...params, resolution: parseFloat(e.target.value)})}
                  />
                </div>
                <button
                  style={processing ? styles.btnDisabled : styles.btn}
                  onClick={() => handleRerunStage(4)}
                  disabled={processing}
                  style={{ marginTop: 10 }}
                >
                  {processing && <span style={styles.spinner}>⟳</span>}
                  Re-run Clustering
                </button>
              </div>
            )}
          </>
        ) : (
          <>
            <div style={{ display: "flex", gap: 10, marginBottom: 10 }}>
              <input
                type="text"
                value={rawPath}
                onChange={(e) => setRawPath(e.target.value)}
                placeholder="data/pbmc3k_raw.h5ad"
                style={styles.paramInput}
              />
            </div>

            <div
              style={styles.advancedToggle}
              onClick={() => setShowAdvanced(!showAdvanced)}
            >
              {showAdvanced ? "▼" : "▶"} Advanced Parameters
            </div>

            {showAdvanced && (
              <div style={styles.paramGrid}>
                <div>
                  <label style={styles.paramLabel}>Min Genes</label>
                  <input type="number" style={styles.paramInput} value={params.min_genes}
                         onChange={(e) => setParams({...params, min_genes: parseInt(e.target.value)})} />
                </div>
                <div>
                  <label style={styles.paramLabel}>Max Genes</label>
                  <input type="number" style={styles.paramInput} value={params.max_genes}
                         onChange={(e) => setParams({...params, max_genes: parseInt(e.target.value)})} />
                </div>
                <div>
                  <label style={styles.paramLabel}>Max MT %</label>
                  <input type="number" style={styles.paramInput} value={params.max_pct_mt}
                         onChange={(e) => setParams({...params, max_pct_mt: parseFloat(e.target.value)})} />
                </div>
                <div>
                  <label style={styles.paramLabel}>N PCs</label>
                  <input type="number" style={styles.paramInput} value={params.n_pcs}
                         onChange={(e) => setParams({...params, n_pcs: parseInt(e.target.value)})} />
                </div>
              </div>
            )}

            <button
              style={processing || !rawPath ? styles.btnDisabled : styles.btn}
              onClick={handleStartAnalysis}
              disabled={processing || !rawPath}
            >
              {processing && <span style={styles.spinner}>⟳</span>}
              {processing ? "Starting..." : "Run Full Analysis"}
            </button>
          </>
        )}

        {error && <p style={styles.error}>{error}</p>}
        {successMsg && <p style={styles.success}>{successMsg}</p>}
      </div>

      {/* QC Metrics */}
      <div style={styles.section}>
        <div style={styles.sectionTitle}>QC Metrics</div>
        {!qc && <div style={{ color: "#a0aec0", fontSize: 13 }}>Loading...</div>}
        {qc && (
          <div style={styles.grid}>
            <Metric label="Cells" value={m.n_cells?.toLocaleString()} />
            <Metric label="Genes" value={m.n_genes?.toLocaleString()} />
            <Metric label="Median genes / cell" value={m.median_genes_per_cell} />
            <Metric label="Median counts / cell" value={m.median_counts_per_cell} />
            <Metric label="Median MT %" value={m.median_pct_mt != null ? `${m.median_pct_mt}%` : null} />
            <Metric label="Predicted doublets" value={
              m.n_predicted_doublets != null
                ? `${m.n_predicted_doublets} (${m.pct_predicted_doublets}%)`
                : null
            } />
          </div>
        )}
      </div>

      {/* Similar Runs */}
      <div style={styles.section}>
        <div style={styles.sectionTitle}>Similar Runs</div>
        {sims === null && <div style={{ color: "#a0aec0", fontSize: 13 }}>Loading...</div>}
        {sims && sims.length === 0 && (
          <div>
            <p style={{ fontSize: 13, color: "#718096", marginBottom: 10 }}>
              Not yet indexed — compute the embedding vector first.
            </p>
            <button
              style={processing ? styles.btnDisabled : styles.btn}
              onClick={handleComputeVector}
              disabled={processing}
            >
              {processing && <span style={styles.spinner}>⟳</span>}
              {processing ? "Indexing..." : "Compute vector"}
            </button>
          </div>
        )}
        {sims && sims.map(s => (
          <div key={s.run_id} style={styles.simRow}>
            <span style={styles.simId}>{s.run_id.slice(0, 16)}...</span>
            <span style={styles.simScore}>{(s.similarity * 100).toFixed(1)}% similar</span>
          </div>
        ))}
      </div>

      {/* Visualization */}
      <div style={styles.section}>
        <div style={styles.sectionTitle}>Cell Visualization</div>
        <UMAPViewer runId={run.id} token={token} />
      </div>
    </div>
  );
}