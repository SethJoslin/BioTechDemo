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
  return fetch(`${BASE}/token`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username }),
  }).then(handle);
}

export async function fetchRuns(token) {
  return fetch(`${BASE}/runs`, { headers: authHeaders(token) }).then(handle);
}

export async function fetchRun(token, runId) {
  return fetch(`${BASE}/runs/${runId}`, { headers: authHeaders(token) }).then(handle);
}

export async function fetchQC(token, runId) {
  return fetch(`${BASE}/runs/${runId}/qc`, { headers: authHeaders(token) }).then(handle);
}

export async function fetchSimilarity(token, runId, k = 5) {
  return fetch(`${BASE}/similarity/${runId}?k=${k}`, {
    headers: authHeaders(token),
  }).then(handle);
}

export async function computeVector(token, runId) {
  return fetch(`${BASE}/runs/${runId}/compute_vector`, {
    method: "POST",
    headers: authHeaders(token),
  }).then(handle);
}
