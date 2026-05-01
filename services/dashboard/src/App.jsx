import { useState, useEffect } from "react";
import { fetchRuns, fetchEmbeddings, fetchFeatures } from "./api";
import RunList from "./components/RunList";
import UMAPViewer from "./components/UMAPViewer";
import FeatureSummary from "./components/FeatureSummary";

export default function App() {
  const [runs, setRuns] = useState([]);
  const [selected, setSelected] = useState(null);
  const [emb, setEmb] = useState(null);
  const [stats, setStats] = useState(null);

  useEffect(() => { fetchRuns().then(setRuns); }, []);

  useEffect(() => {
    if (!selected) return;
    fetchEmbeddings(selected).then(setEmb);
    fetchFeatures(selected).then(setStats);
  }, [selected]);

  return (
    <div>
      <RunList runs={runs} onSelect={setSelected} />
      <UMAPViewer data={emb} />
      <FeatureSummary stats={stats} />
    </div>
  );
}
