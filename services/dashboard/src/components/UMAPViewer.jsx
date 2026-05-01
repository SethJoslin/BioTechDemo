import React from "react";
import Plot from "react-plotly.js";

export default function UMAPViewer({ data }) {
  if (!data) return <div>Loading embeddings…</div>;

  // Expecting data to be an array of rows with numeric columns
  const keys = Object.keys(data[0]).filter(
    (k) => typeof data[0][k] === "number"
  );

  if (keys.length < 2) {
    return <div style={{ color: "crimson" }}>Not enough numeric columns</div>;
  }

  const xKey = keys[0];
  const yKey = keys[1];

  const x = data.map((r) => r[xKey]);
  const y = data.map((r) => r[yKey]);

  return (
    <Plot
      data={[
        {
          x,
          y,
          mode: "markers",
          type: "scattergl",
          marker: { size: 6, opacity: 0.8, color: "rgb(31,119,180)" },
        },
      ]}
      layout={{
        title: "UMAP / Embeddings Scatter",
        xaxis: { title: xKey },
        yaxis: { title: yKey },
        autosize: true,
        margin: { t: 40, l: 40, r: 20, b: 40 },
      }}
      style={{ width: "100%", height: "600px" }}
      config={{ responsive: true }}
    />
  );
}
