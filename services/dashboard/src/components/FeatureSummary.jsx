export default function FeatureSummary({ stats }) {
  if (!stats) return null;

  return (
    <div>
      <p>Cells: {stats.n_cells}</p>
      <p>Genes: {stats.n_genes}</p>
      <p>HVGs: {stats.n_hvgs}</p>
    </div>
  );
}
