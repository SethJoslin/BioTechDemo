import { useState } from "react";
import { getToken } from "./api";
import RunList from "./components/RunList";
import RunDetail from "./components/RunDetail";

const styles = {
  app: { fontFamily: "sans-serif", maxWidth: 1100, margin: "0 auto", padding: 24 },
  header: { borderBottom: "2px solid #e2e8f0", paddingBottom: 12, marginBottom: 24 },
  title: { fontSize: 22, fontWeight: 700, color: "#1a202c", margin: 0 },
  subtitle: { fontSize: 13, color: "#718096", marginTop: 4 },
  layout: { display: "grid", gridTemplateColumns: "320px 1fr", gap: 24 },
  loginWrap: { maxWidth: 360, margin: "80px auto", textAlign: "center" },
  input: { width: "100%", padding: "8px 12px", border: "1px solid #cbd5e0",
           borderRadius: 6, fontSize: 14, marginBottom: 10, boxSizing: "border-box" },
  btn: { width: "100%", padding: "9px 0", background: "#3182ce", color: "#fff",
         border: "none", borderRadius: 6, fontSize: 14, cursor: "pointer" },
  error: { color: "#e53e3e", fontSize: 13, marginTop: 8 },
};

export default function App() {
  const [token, setToken] = useState(null);
  const [username, setUsername] = useState("");
  const [loginError, setLoginError] = useState(null);
  const [selectedRun, setSelectedRun] = useState(null);

  async function handleLogin(e) {
    e.preventDefault();
    setLoginError(null);
    try {
      const { access_token } = await getToken(username);
      setToken(access_token);
    } catch {
      setLoginError("Login failed — is the API running?");
    }
  }

  if (!token) {
    return (
      <div style={styles.loginWrap}>
        <h2 style={{ marginBottom: 20 }}>OpenBioOps</h2>
        <form onSubmit={handleLogin}>
          <input
            style={styles.input}
            placeholder="Username"
            value={username}
            onChange={e => setUsername(e.target.value)}
          />
          <button style={styles.btn} type="submit">Sign in</button>
        </form>
        {loginError && <p style={styles.error}>{loginError}</p>}
      </div>
    );
  }

  return (
    <div style={styles.app}>
      <div style={styles.header}>
        <h1 style={styles.title}>OpenBioOps</h1>
        <p style={styles.subtitle}>
          Logged in as <strong>{username}</strong>
          <button
            onClick={() => { setToken(null); setSelectedRun(null); }}
            style={{ marginLeft: 12, fontSize: 12, color: "#718096",
                     background: "none", border: "none", cursor: "pointer" }}
          >
            Sign out
          </button>
        </p>
      </div>
      <div style={styles.layout}>
        <RunList token={token} selected={selectedRun} onSelect={setSelectedRun} />
        <RunDetail token={token} run={selectedRun} />
      </div>
    </div>
  );
}
