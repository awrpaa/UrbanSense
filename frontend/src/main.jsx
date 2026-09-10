import React, { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import "./styles.css";

const API = import.meta.env.VITE_API_URL || "http://localhost:8000";

function Stat({ label, value, sub }) {
  return <div className="stat"><span>{label}</span><strong>{value}</strong><small>{sub}</small></div>;
}

function App() {
  const [health, setHealth] = useState(null);
  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      fetch(`${API}/api/health`).then(r => r.json()),
      fetch(`${API}/api/events/validate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ events: [] })
      }).then(r => r.json())
    ]).then(([h, e]) => {
      setHealth(h);
      setEvents(e.events || []);
    }).catch(() => {}).finally(() => setLoading(false));
  }, []);

  return <main>
    <header>
      <div><p className="eyebrow">URBAN INTELLIGENCE PLATFORM</p><h1>UrbanSense</h1></div>
      <div className="status"><i /> {health?.status === "ok" ? "SYSTEM ONLINE" : "CONNECTING"}</div>
    </header>

    <section className="hero"><div><p className="eyebrow">COMMAND CENTER</p><h2>Detect. Verify. Localize. Act.</h2><p>Unified road, traffic and motor-vehicle intelligence from the public-transport sensing network.</p></div><div className="fleet"><span>FLEET SENSING</span><b>READY</b></div></section>

    <section className="stats">
      <Stat label="ROAD DEFECTS" value="—" sub="Tier 1" />
      <Stat label="CONGESTION" value="—" sub="Tier 2" />
      <Stat label="MVA EVENTS" value="—" sub="Tier 3" />
      <Stat label="ACTIVE EVENTS" value={loading ? "…" : events.length} sub="Unified event stream" />
    </section>

    <section className="grid">
      <div className="map"><div className="mapgrid"><span className="pin p1"/><span className="pin p2"/><span className="pin p3"/></div><div className="maplabel">GIS INTELLIGENCE MAP <small>Map provider can be attached here</small></div></div>
      <div className="panel"><div className="panelhead"><h3>EVENT FEED</h3><span>LIVE</span></div>{events.length ? events.map(e => <article key={e.event_id}><b>{e.event_type}</b><small>Tier {e.tier} · {e.severity || "UNSPECIFIED"}</small></article>) : <div className="empty">No events received yet.<br/><small>Connect the model adapters to populate the operational feed.</small></div>}</div>
    </section>

    <footer><span>URBANSENSE · SIH 2026</span><span>{health?.pipeline || "tier1-tier2-tier3"}</span></footer>
  </main>;
}

createRoot(document.getElementById("root")).render(<App />);
