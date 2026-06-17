/**
 * Interactive UMAP Viewer Component
 *
 * Provides scatter plot visualization of single-cell embeddings with:
 * - Cluster coloring
 * - Gene expression overlay
 * - Interactive tooltips
 * - Cell selection
 */
import React, { useState, useEffect, useMemo, useCallback } from "react";
import Plot from "react-plotly.js";
import { fetchUMAP, fetchGeneExpression, fetchGenes, fetchClusters } from "../api";

// ── Color Palettes ───────────────────────────────────────────────────────────

const CLUSTER_COLORS = [
  "#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd",
  "#8c564b", "#e377c2", "#7f7f7f", "#bcbd22", "#17becf",
  "#aec7e8", "#ffbb78", "#98df8a", "#ff9896", "#c5b0d5",
  "#c49c94", "#f7b6d2", "#c7c7c7", "#dbdb8d", "#9edae5",
];

function getExpressionColor(value, min, max) {
  const t = max > min ? (value - min) / (max - min) : 0;
  // Blue to Yellow gradient (common in scRNA-seq)
  const r = Math.round(255 * t);
  const g = Math.round(255 * t);
  const b = Math.round(255 * (1 - t));
  return `rgb(${r},${g},${b})`;
}

// ── Styles ───────────────────────────────────────────────────────────────────

const styles = {
  container: {
    display: "flex",
    flexDirection: "column",
    gap: 16,
    width: "100%",
  },
  controls: {
    display: "flex",
    flexWrap: "wrap",
    gap: 12,
    alignItems: "center",
    padding: "12px 16px",
    background: "#f8fafc",
    borderRadius: 8,
    border: "1px solid #e2e8f0",
  },
  controlGroup: {
    display: "flex",
    alignItems: "center",
    gap: 8,
  },
  label: {
    fontSize: 13,
    fontWeight: 500,
    color: "#4a5568",
  },
  select: {
    padding: "6px 10px",
    fontSize: 13,
    border: "1px solid #cbd5e0",
    borderRadius: 6,
    background: "#fff",
    minWidth: 120,
  },
  input: {
    padding: "6px 10px",
    fontSize: 13,
    border: "1px solid #cbd5e0",
    borderRadius: 6,
    width: 180,
  },
  geneList: {
    position: "absolute",
    top: "100%",
    left: 0,
    right: 0,
    background: "#fff",
    border: "1px solid #cbd5e0",
    borderRadius: 6,
    maxHeight: 200,
    overflow: "auto",
    zIndex: 100,
    boxShadow: "0 4px 12px rgba(0,0,0,0.1)",
  },
  geneItem: {
    padding: "8px 12px",
    fontSize: 13,
    cursor: "pointer",
    borderBottom: "1px solid #f0f0f0",
  },
  geneItemHover: {
    background: "#f0f4ff",
  },
  legend: {
    display: "flex",
    flexWrap: "wrap",
    gap: 8,
    padding: "8px 12px",
    background: "#f8fafc",
    borderRadius: 6,
    fontSize: 12,
  },
  legendItem: {
    display: "flex",
    alignItems: "center",
    gap: 4,
    cursor: "pointer",
  },
  legendDot: {
    width: 12,
    height: 12,
    borderRadius: "50%",
  },
  stats: {
    display: "flex",
    gap: 20,
    fontSize: 12,
    color: "#718096",
    padding: "8px 0",
  },
  loading: {
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    height: 400,
    color: "#a0aec0",
    fontSize: 14,
  },
  error: {
    color: "#e53e3e",
    background: "#fff5f5",
    padding: 12,
    borderRadius: 6,
    fontSize: 13,
  },
};

// ── Main Component ───────────────────────────────────────────────────────────

export default function UMAPViewer({ runId, token, data: propData }) {
  // State
  const [umapData, setUmapData] = useState(null);
  const [clusterInfo, setClusterInfo] = useState(null);
  const [colorMode, setColorMode] = useState("cluster"); // "cluster" | "expression"
  const [selectedGene, setSelectedGene] = useState("");
  const [geneSearch, setGeneSearch] = useState("");
  const [geneResults, setGeneResults] = useState([]);
  const [geneExpression, setGeneExpression] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [hiddenClusters, setHiddenClusters] = useState(new Set());
  const [showGeneDropdown, setShowGeneDropdown] = useState(false);

  // Fetch UMAP data when runId changes
  useEffect(() => {
    if (!runId || !token) {
      // Fall back to prop data if no runId
      if (propData) {
        const keys = Object.keys(propData[0] || {}).filter(
          (k) => typeof propData[0][k] === "number"
        );
        if (keys.length >= 2) {
          const coords = propData.map((r, i) => ({
            cell_id: r.cell_id || `cell_${i}`,
            x: r[keys[0]],
            y: r[keys[1]],
            cluster: r.cluster || 0,
          }));
          setUmapData({ coordinates: coords, clusters: [...new Set(coords.map(c => c.cluster))] });
        }
      }
      return;
    }

    setLoading(true);
    setError(null);

    Promise.all([
      fetchUMAP(token, runId),
      fetchClusters(token, runId).catch(() => null),
    ])
      .then(([umap, clusters]) => {
        setUmapData(umap);
        setClusterInfo(clusters);
      })
      .catch((e) => {
        // Suppress 404 errors - UMAP might not exist yet if analysis hasn't completed
        if (e.message && !e.message.includes('404')) {
          setError(e.message);
        }
        // If 404, leave umapData as null and show placeholder below
      })
      .finally(() => setLoading(false));
  }, [runId, token, propData]);

  // Search genes
  useEffect(() => {
    if (!geneSearch || !runId || !token) {
      setGeneResults([]);
      return;
    }

    const timeout = setTimeout(() => {
      fetchGenes(token, runId, geneSearch, 20)
        .then((res) => setGeneResults(res.genes || []))
        .catch(() => setGeneResults([]));
    }, 300); // Debounce

    return () => clearTimeout(timeout);
  }, [geneSearch, runId, token]);

  // Fetch gene expression when gene selected
  useEffect(() => {
    if (!selectedGene || !runId || !token) {
      setGeneExpression(null);
      return;
    }

    setLoading(true);
    fetchGeneExpression(token, runId, selectedGene)
      .then(setGeneExpression)
      .catch((e) => {
        setError(`Failed to load expression for ${selectedGene}`);
        setGeneExpression(null);
      })
      .finally(() => setLoading(false));
  }, [selectedGene, runId, token]);

  // Toggle cluster visibility
  const toggleCluster = useCallback((clusterId) => {
    setHiddenClusters((prev) => {
      const next = new Set(prev);
      if (next.has(clusterId)) {
        next.delete(clusterId);
      } else {
        next.add(clusterId);
      }
      return next;
    });
  }, []);

  // Prepare plot data
  const plotData = useMemo(() => {
    if (!umapData?.coordinates) return [];

    const coords = umapData.coordinates.filter(
      (c) => !hiddenClusters.has(c.cluster)
    );

    if (colorMode === "expression" && geneExpression?.expression) {
      // Color by gene expression
      const expr = geneExpression.expression;
      const min = geneExpression.min_value;
      const max = geneExpression.max_value;

      return [
        {
          x: coords.map((c) => c.x),
          y: coords.map((c) => c.y),
          mode: "markers",
          type: "scattergl",
          marker: {
            size: 4,
            opacity: 0.8,
            color: coords.map((c, i) => {
              const idx = umapData.coordinates.indexOf(c);
              return expr[idx] ?? 0;
            }),
            colorscale: "YlGnBu",
            reversescale: true,
            colorbar: {
              title: selectedGene,
              thickness: 15,
              len: 0.5,
            },
            cmin: min,
            cmax: max,
          },
          text: coords.map((c, i) => {
            const idx = umapData.coordinates.indexOf(c);
            return `Cell: ${c.cell_id}<br>Cluster: ${c.cluster}<br>${selectedGene}: ${(expr[idx] ?? 0).toFixed(2)}`;
          }),
          hoverinfo: "text",
        },
      ];
    }

    // Color by cluster
    const clusterGroups = {};
    coords.forEach((c) => {
      if (!clusterGroups[c.cluster]) {
        clusterGroups[c.cluster] = { x: [], y: [], text: [] };
      }
      clusterGroups[c.cluster].x.push(c.x);
      clusterGroups[c.cluster].y.push(c.y);
      clusterGroups[c.cluster].text.push(
        `Cell: ${c.cell_id}<br>Cluster: ${c.cluster}${c.cell_type ? `<br>Type: ${c.cell_type}` : ""}`
      );
    });

    return Object.entries(clusterGroups).map(([cluster, data]) => ({
      x: data.x,
      y: data.y,
      mode: "markers",
      type: "scattergl",
      name: `Cluster ${cluster}`,
      marker: {
        size: 4,
        opacity: 0.8,
        color: CLUSTER_COLORS[parseInt(cluster) % CLUSTER_COLORS.length],
      },
      text: data.text,
      hoverinfo: "text",
    }));
  }, [umapData, colorMode, geneExpression, selectedGene, hiddenClusters]);

  // Render loading state
  if (loading && !umapData) {
    return <div style={styles.loading}>Loading UMAP coordinates...</div>;
  }

  // Render error state
  if (error && !umapData) {
    return <div style={styles.error}>Error: {error}</div>;
  }

  // Render empty state
  if (!umapData?.coordinates?.length) {
    return (
      <div style={styles.loading}>
        {loading
          ? "Loading UMAP coordinates..."
          : "No UMAP data available. Run analysis to generate visualization."}
      </div>
    );
  }

  const nCells = umapData.coordinates.length;
  const nClusters = umapData.clusters?.length || 0;
  const visibleCells = nCells - umapData.coordinates.filter(c => hiddenClusters.has(c.cluster)).length;

  return (
    <div style={styles.container}>
      {/* Controls */}
      <div style={styles.controls}>
        <div style={styles.controlGroup}>
          <span style={styles.label}>Color by:</span>
          <select
            style={styles.select}
            value={colorMode}
            onChange={(e) => setColorMode(e.target.value)}
          >
            <option value="cluster">Cluster</option>
            <option value="expression">Gene Expression</option>
          </select>
        </div>

        {colorMode === "expression" && (
          <div style={{ ...styles.controlGroup, position: "relative" }}>
            <span style={styles.label}>Gene:</span>
            <input
              style={styles.input}
              type="text"
              placeholder="Search genes..."
              value={geneSearch}
              onChange={(e) => {
                setGeneSearch(e.target.value);
                setShowGeneDropdown(true);
              }}
              onFocus={() => setShowGeneDropdown(true)}
              onBlur={() => setTimeout(() => setShowGeneDropdown(false), 200)}
            />
            {showGeneDropdown && geneResults.length > 0 && (
              <div style={styles.geneList}>
                {geneResults.map((gene) => (
                  <div
                    key={gene}
                    style={styles.geneItem}
                    onMouseDown={() => {
                      setSelectedGene(gene);
                      setGeneSearch(gene);
                      setShowGeneDropdown(false);
                    }}
                  >
                    {gene}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {selectedGene && geneExpression && (
          <div style={styles.stats}>
            <span>Min: {geneExpression.min_value.toFixed(2)}</span>
            <span>Max: {geneExpression.max_value.toFixed(2)}</span>
            <span>Mean: {geneExpression.mean_value.toFixed(2)}</span>
          </div>
        )}
      </div>

      {/* Stats */}
      <div style={styles.stats}>
        <span>{visibleCells.toLocaleString()} / {nCells.toLocaleString()} cells</span>
        <span>{nClusters} clusters</span>
        {loading && <span style={{ color: "#3182ce" }}>Loading...</span>}
      </div>

      {/* Cluster Legend */}
      {colorMode === "cluster" && umapData.clusters && (
        <div style={styles.legend}>
          {umapData.clusters.map((cluster) => {
            const isHidden = hiddenClusters.has(cluster);
            const clusterMeta = clusterInfo?.clusters?.find(c => c.cluster_id === cluster);
            return (
              <div
                key={cluster}
                style={{
                  ...styles.legendItem,
                  opacity: isHidden ? 0.4 : 1,
                }}
                onClick={() => toggleCluster(cluster)}
                title={clusterMeta?.cell_type || `Cluster ${cluster}`}
              >
                <div
                  style={{
                    ...styles.legendDot,
                    background: CLUSTER_COLORS[cluster % CLUSTER_COLORS.length],
                  }}
                />
                <span>
                  {clusterMeta?.cell_type || `C${cluster}`}
                  {clusterMeta && ` (${clusterMeta.percentage}%)`}
                </span>
              </div>
            );
          })}
        </div>
      )}

      {/* Plot */}
      <Plot
        data={plotData}
        layout={{
          title: colorMode === "expression" && selectedGene
            ? `UMAP - ${selectedGene} Expression`
            : "UMAP Projection",
          xaxis: {
            title: "UMAP 1",
            zeroline: false,
            showgrid: false,
          },
          yaxis: {
            title: "UMAP 2",
            zeroline: false,
            showgrid: false,
            scaleanchor: "x",
          },
          autosize: true,
          margin: { t: 50, l: 60, r: 20, b: 50 },
          showlegend: colorMode === "cluster",
          legend: {
            orientation: "h",
            y: -0.15,
          },
          hovermode: "closest",
          paper_bgcolor: "rgba(0,0,0,0)",
          plot_bgcolor: "rgba(0,0,0,0)",
        }}
        style={{ width: "100%", height: "600px" }}
        config={{
          responsive: true,
          displayModeBar: true,
          modeBarButtonsToRemove: ["lasso2d", "select2d"],
          toImageButtonOptions: {
            format: "svg",
            filename: `umap_${runId || "plot"}`,
          },
        }}
        useResizeHandler
      />

      {error && <div style={styles.error}>{error}</div>}
    </div>
  );
}
