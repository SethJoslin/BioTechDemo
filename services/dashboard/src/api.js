const BASE = process.env.REACT_APP_API_URL || "http://localhost:8000";

function authHeaders(token) {
  return {
    "Content-Type": "application/json",
    "Authorization": `Bearer ${token}`,
  };
}

async function handle(res) {
  if (!res.ok) throw new Error(`${res.status} ${res.url}`);
  return res.json();
}

export async function getToken(username) {
  return fetch(`${BASE}/v1/auth/token`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username }),
  }).then(handle);
}

export async function fetchRuns(token) {
  return fetch(`${BASE}/v1/runs`, { headers: authHeaders(token) })
    .then(handle)
    .then(data => data.runs);
}

export async function createRun(token, data) {
  return fetch(`${BASE}/v1/runs`, {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify(data),
  }).then(handle);
}

export async function fetchRun(token, runId) {
  return fetch(`${BASE}/v1/runs/${runId}`, { headers: authHeaders(token) }).then(handle);
}

export async function deleteRun(token, runId) {
  return fetch(`${BASE}/v1/runs/${runId}`, {
    method: "DELETE",
    headers: authHeaders(token),
  }).then(res => {
    if (!res.ok) throw new Error(`${res.status} ${res.url}`);
    return res.status === 204 ? null : res.json();
  });
}

export async function fetchQC(token, runId) {
  return fetch(`${BASE}/v1/runs/${runId}/qc`, { headers: authHeaders(token) }).then(handle);
}

export async function fetchSimilarity(token, runId, k = 5) {
  return fetch(`${BASE}/v1/similarity/${runId}?k=${k}`, {
    headers: authHeaders(token),
  }).then(handle);
}

export async function computeVector(token, runId) {
  return fetch(`${BASE}/v1/runs/${runId}/compute_vector`, {
    method: "POST",
    headers: authHeaders(token),
  }).then(handle);
}

export async function extractFeatures(token, runId, rawPath) {
  return fetch(`${BASE}/v1/runs/${runId}/features`, {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify({ raw_path: rawPath }),
  }).then(handle);
}

// ── Visualization API v1 ─────────────────────────────────────────────────────

export async function fetchUMAP(token, runId) {
  return fetch(`${BASE}/v1/viz/${runId}/umap`, {
    headers: authHeaders(token),
  }).then(handle);
}

export async function fetchGeneExpression(token, runId, gene) {
  return fetch(`${BASE}/v1/viz/${runId}/expression/${encodeURIComponent(gene)}`, {
    headers: authHeaders(token),
  }).then(handle);
}

export async function fetchGenes(token, runId, search = "", limit = 100) {
  const params = new URLSearchParams({ limit: String(limit) });
  if (search) params.set("search", search);
  return fetch(`${BASE}/v1/viz/${runId}/genes?${params}`, {
    headers: authHeaders(token),
  }).then(handle);
}

export async function fetchClusters(token, runId) {
  return fetch(`${BASE}/v1/viz/${runId}/clusters`, {
    headers: authHeaders(token),
  }).then(handle);
}

export async function fetchDifferentialExpression(token, runId, group1, group2, topN = 50) {
  const params = new URLSearchParams({
    group1,
    group2,
    top_n: String(topN),
  });
  return fetch(`${BASE}/v1/viz/${runId}/differential?${params}`, {
    method: "POST",
    headers: authHeaders(token),
  }).then(handle);
}

// ── Workflow API v1 ──────────────────────────────────────────────────────────

export async function fetchWorkflowTemplates(token) {
  return fetch(`${BASE}/v1/workflows/templates`, {
    headers: authHeaders(token),
  }).then(handle);
}

export async function submitWorkflow(token, request) {
  return fetch(`${BASE}/v1/workflows`, {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify(request),
  }).then(handle);
}

export async function fetchWorkflowStatus(token, executionId, engine = "nextflow") {
  return fetch(`${BASE}/v1/workflows/${executionId}?engine=${engine}`, {
    headers: authHeaders(token),
  }).then(handle);
}

export async function cancelWorkflow(token, executionId, engine = "nextflow") {
  return fetch(`${BASE}/v1/workflows/${executionId}/cancel?engine=${engine}`, {
    method: "POST",
    headers: authHeaders(token),
  }).then(handle);
}

// ── Analysis Pipeline API (Prefect) ──────────────────────────────────────────

export async function startAnalysis(token, runId, rawPath, params = null) {
  return fetch(`${BASE}/v1/runs/${runId}/analysis/start`, {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify({ raw_path: rawPath, params }),
  }).then(handle);
}

export async function getAnalysisStatus(token, runId) {
  return fetch(`${BASE}/v1/runs/${runId}/analysis/status`, {
    headers: authHeaders(token),
  }).then(handle);
}

export async function rerunStage(token, runId, stage, params = null) {
  return fetch(`${BASE}/v1/runs/${runId}/analysis/rerun-stage`, {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify({ stage, params }),
  }).then(handle);
}