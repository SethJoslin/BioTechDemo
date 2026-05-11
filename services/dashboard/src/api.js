const BASE = process.env.REACT_APP_API_URL || "http://localhost:8000";

function handleResponse(r) {
  if (!r.ok) throw new Error(`API error ${r.status}: ${r.url}`);
  return r.json();
}

export async function fetchRuns() {
  return fetch(`${BASE}/runs`).then(handleResponse);
}

export async function fetchRun(runId) {
  return fetch(`${BASE}/runs/${runId}`).then(handleResponse);
}

export async function computeVector(runId) {
  return fetch(`${BASE}/runs/${runId}/compute_vector`, {
    method: "POST",
  }).then(handleResponse);
}

export async function fetchSimilarity(runId, k = 5) {
  return fetch(`${BASE}/similarity/${runId}?k=${k}`).then(handleResponse);
}