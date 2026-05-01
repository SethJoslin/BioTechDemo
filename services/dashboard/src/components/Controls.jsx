// services/dashboard/src/components/Controls.jsx
import React from 'react';

export default function Controls({ limit, setLimit, onRefresh }) {
  return (
    <div style={{ display: 'flex', gap: 12, alignItems: 'center', marginBottom: 12 }}>
      <label>
        Sample size
        <select value={limit} onChange={e => setLimit(Number(e.target.value))} style={{ marginLeft: 8 }}>
          <option value={200}>200</option>
          <option value={500}>500</option>
          <option value={1000}>1000</option>
        </select>
      </label>
      <button onClick={onRefresh}>Refresh</button>
      <a href="/umap" target="_blank" rel="noreferrer">Open UMAP PNG</a>
    </div>
  );
}
