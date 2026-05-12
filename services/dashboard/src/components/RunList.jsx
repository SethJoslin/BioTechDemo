import { useState, useEffect } from "react";
import { fetchRuns } from "../api";

const QC_COLORS = { pass: "#38a169", fail: "#e53e3e", warn: "#d69e2e", unknown: "#a0aec0" };

const styles = {
  wrap: { border: "1px solid #e2e8f0", borderRadius: 8, overflow: "hidden" },
  header: { padding: "12px 16px", background: "#f7fafc", borderBottom: "1px solid #e2e8f0",
            fontWeight: 600, fontSize: 14, display: "flex", justifyContent: "space-between" },
  refresh: { fontSize: 12, color: "#3182ce", background: "none",
             border: "none", cursor: "pointer" },
  row: { padding: "12px 16px", borderBottom: "1px solid #f0f4f8",
         cursor: "pointer", transition: "background 0.1s" },
  name: { fontWeight: 500, fontSize: 14, marginBottom: 3 },
  meta: { fontSize: 12, color: "#718096" },
  badge: { display: "inline-block", padding: "2px 8px", borderRadius: 99,
           fontSize: 11, fontWeight: 600, color: "#fff", marginLeft: 8 },
  empty: { padding: 24, textAlign: "center", color: "#a0aec0", fontSize: 14 },
};

export default function RunList({ token, selected, onSelect }) {
  const [runs, setRuns] = useState([]);
  const [loading, setLoading] = useState(true);

  function load() {
    setLoading(true);
    fetchRuns(token)
      .then(setRuns)
      .finally(() => setLoading(false));
  }

  useEffect(load, [token]);

  return (
    <div style={styles.wrap}>
      <div style={styles.header}>
        Runs ({runs.length})
        <button style={styles.refresh} onClick={load}>↻ Refresh</button>
      </div>
      {loading && <div style={styles.empty}>Loading...</div>}
      {!loading && runs.length === 0 && <div style={styles.empty}>No runs yet.</div>}
      {runs.map(run => (
        <div
          key={run.id}
          style={{ ...styles.row, background: selected?.id === run.id ? "#ebf8ff" : "#fff" }}
          onClick={() => onSelect(run)}
        >
          <div style={styles.name}>
            {run.name}
            <span style={{ ...styles.badge, background: QC_COLORS[run.qc?.status] || QC_COLORS.unknown }}>
              {run.qc?.status || "unknown"}
            </span>
          </div>
          <div style={styles.meta}>
            {run.id.slice(0, 8)}... &middot; {new Date(run.created_at).toLocaleDateString()}
          </div>
        </div>
      ))}
    </div>
  );
}
