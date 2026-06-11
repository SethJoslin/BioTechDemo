// services/dashboard/src/components/DashboardPage.jsx
import React, { useState } from 'react';
import EmbeddingsPlot from './EmbeddingsPlot';
import Controls from './Controls';

export default function DashboardPage() {
  const [limit, setLimit] = useState(500);
  const [refreshKey, setRefreshKey] = useState(0);

  return (
    <div style={{ padding: 20 }}>
      <h2>OpenBioOps Dashboard</h2>
      <Controls limit={limit} setLimit={setLimit} onRefresh={() => setRefreshKey(k => k + 1)} />
      <EmbeddingsPlot key={refreshKey + '-' + limit} limit={limit} />
    </div>
  );
}
