import { useState, useEffect } from "react";
import { fetchRuns, createRun } from "../api";

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
  createForm: { padding: 16, background: "#f7fafc", borderBottom: "1px solid #e2e8f0" },
  input: { width: "100%", padding: "6px 10px", border: "1px solid #cbd5e0",
           borderRadius: 4, fontSize: 13, marginBottom: 8, boxSizing: "border-box" },
  btnPrimary: { padding: "6px 12px", background: "#3182ce", color: "#fff",
                border: "none", borderRadius: 4, fontSize: 12, cursor: "pointer", marginRight: 6 },
  btnSecondary: { padding: "6px 12px", background: "#e2e8f0", color: "#2d3748",
                  border: "none", borderRadius: 4, fontSize: 12, cursor: "pointer" },
  btnAdd: { fontSize: 12, color: "#3182ce", background: "none",
            border: "none", cursor: "pointer", marginLeft: 8 },
  error: { color: "#e53e3e", fontSize: 12, marginTop: 6 },
};

export default function RunList({ token, selected, onSelect }) {
  const [runs, setRuns] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [newRunName, setNewRunName] = useState("");
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState(null);

  function load() {
    setLoading(true);
    fetchRuns(token)
      .then(setRuns)
      .finally(() => setLoading(false));
  }

  useEffect(load, [token]);

  async function handleCreate(e) {
    e.preventDefault();
    if (!newRunName.trim()) return;

    setCreating(true);
    setError(null);
    try {
      const newRun = await createRun(token, { name: newRunName.trim() });
      setRuns([newRun, ...runs]);
      setNewRunName("");
      setShowForm(false);
      onSelect(newRun);
    } catch (err) {
      setError(err.message || "Failed to create run");
    } finally {
      setCreating(false);
    }
  }

  return (
    <div style={styles.wrap}>
      <div style={styles.header}>
        Runs ({runs.length})
        <div>
          {!showForm && <button style={styles.btnAdd} onClick={() => setShowForm(true)}>+ New</button>}
          <button style={styles.refresh} onClick={load}>↻ Refresh</button>
        </div>
      </div>
      {showForm && (
        <form style={styles.createForm} onSubmit={handleCreate}>
          <input
            style={styles.input}
            placeholder="Run name (e.g., PBMC-3k-Sample-A)"
            value={newRunName}
            onChange={e => setNewRunName(e.target.value)}
            disabled={creating}
            autoFocus
          />
          <button style={styles.btnPrimary} type="submit" disabled={creating}>
            {creating ? "Creating..." : "Create"}
          </button>
          <button
            style={styles.btnSecondary}
            type="button"
            onClick={() => { setShowForm(false); setNewRunName(""); setError(null); }}
            disabled={creating}
          >
            Cancel
          </button>
          {error && <div style={styles.error}>{error}</div>}
        </form>
      )}
      {loading && <div style={styles.empty}>Loading...</div>}
      {!loading && runs.length === 0 && <div style={styles.empty}>No runs yet. Click "+ New" to create one.</div>}
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