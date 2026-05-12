import { useState, useEffect } from "react";
import { fetchQC, fetchSimilarity, computeVector } from "../api";

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
  error: { color: "#e53e3e", fontSize: 13 },
};

function Metric({ label, value }) {
  return (
    <div style={styles.metric}>
      <div style={styles.metricLabel}>{label}</div>
      <div style={styles.metricValue}>{value ?? "—"}</div>
    </div>
  );
}

export default function RunDetail({ token, run }) {
  const [qc, setQC] = useState(null);
  const [sims, setSims] = useState(null);
  const [indexing, setIndexing] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!run) return;
    setQC(null); setSims(null); setError(null);

    fetchQC(token, run.id).then(setQC).catch(() => setQC({}));

    fetchSimilarity(token, run.id).then(setSims).catch(() => setSims([]));
  }, [run, token]);

  async function handleIndex() {
    setIndexing(true); setError(null);
    try {
      await computeVector(token, run.id);
      const results = await fetchSimilarity(token, run.id);
      setSims(results);
    } catch (e) {
      setError("Could not index run — embeddings may not exist yet.");
    } finally {
      setIndexing(false);
    }
  }

  if (!run) {
    return <div style={styles.wrap}><div style={styles.empty}>Select a run to view details</div></div>;
  }

  const m = qc?.metrics || {};

  return (
    <div style={styles.wrap}>
      <div style={styles.title}>{run.name}</div>
      <div style={styles.id}>{run.id}</div>

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

      <div style={styles.section}>
        <div style={styles.sectionTitle}>Similar Runs</div>
        {sims === null && <div style={{ color: "#a0aec0", fontSize: 13 }}>Loading...</div>}
        {sims && sims.length === 0 && (
          <div>
            <p style={{ fontSize: 13, color: "#718096", marginBottom: 10 }}>
              Not yet indexed — compute the embedding vector first.
            </p>
            <button style={styles.btn} onClick={handleIndex} disabled={indexing}>
              {indexing ? "Indexing..." : "Compute vector"}
            </button>
            {error && <p style={styles.error}>{error}</p>}
          </div>
        )}
        {sims && sims.map(s => (
          <div key={s.run_id} style={styles.simRow}>
            <span style={styles.simId}>{s.run_id.slice(0, 16)}...</span>
            <span style={styles.simScore}>{(s.similarity * 100).toFixed(1)}% similar</span>
          </div>
        ))}
      </div>
    </div>
  );
}
