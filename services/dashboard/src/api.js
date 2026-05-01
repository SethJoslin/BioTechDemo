const BASE = process.env.REACT_APP_API_URL;

export async function fetchRuns() {
  return fetch(`${BASE}/runs`).then(r => r.json());
}

export async function fetchEmbeddings(runId) {
  return fetch(`${BASE}/embeddings/${runId}`).then(r => r.json());
}

export async function fetchFeatures(runId) {
  return fetch(`${BASE}/features/${runId}`).then(r => r.json());
}
