import { useState, useEffect } from "react";

const API = "http://127.0.0.1:8000";

export default function App() {
  const [data, setData] = useState(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    const id = setInterval(async () => {
      try {
        const res = await fetch(`${API}/api/telemetry`);
        setData(await res.json());
        setError(false);
      } catch {
        setError(true);
      }
    }, 1000);
    return () => clearInterval(id);
  }, []);

  const card = {
    background: "#1e1e2e",
    borderRadius: 12,
    padding: 20,
    minWidth: 140,
  };

  return (
    <div style={{ padding: 32, color: "white", textAlign: "left" }}>
      <h1>Robot Dashboard</h1>
      <p>{error ? "Backend offline" : "Live telemetry"}</p>
      {data && (
        <div style={{ display: "flex", gap: 16, flexWrap: "wrap" }}>
          <div style={card}>X<h2>{data.x}</h2></div>
          <div style={card}>Y<h2>{data.y}</h2></div>
          <div style={card}>Battery<h2>{data.battery}%</h2></div>
          <div style={card}>Speed<h2>{data.speed} m/s</h2></div>
        </div>
      )}
    </div>
  );
}