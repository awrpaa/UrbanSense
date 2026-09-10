import React, { useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import "./styles.css";

const API = import.meta.env.VITE_API_URL || "http://localhost:8000";

const demoEvents = [
  { id: "EVT-001", type: "Road Damage", title: "Pothole detected", place: "Park Street", bus: "Bus #07", time: "11:23 AM", severity: "Medium", tone: "blue", thumb: "road" },
  { id: "EVT-002", type: "Traffic Anomaly", title: "High vehicle density", place: "AJC Bose Road", bus: "Bus #03", time: "11:17 AM", severity: "Low", tone: "green", thumb: "traffic" },
  { id: "EVT-003", type: "MVA / Violation", title: "No helmet detected", place: "EM Bypass", bus: "Bus #12", time: "11:12 AM", severity: "High", tone: "yellow", thumb: "helmet" },
  { id: "EVT-004", type: "Road Damage", title: "Transverse crack", place: "Garia", bus: "Bus #05", time: "11:08 AM", severity: "Low", tone: "blue", thumb: "crack" },
];

const mapMarkers = [
  { x: 27, y: 33, kind: "road", label: "Pothole · Park Street" },
  { x: 42, y: 24, kind: "traffic", label: "Congestion · AJC Bose Road" },
  { x: 56, y: 36, kind: "mva", label: "MVA · EM Bypass" },
  { x: 69, y: 28, kind: "road", label: "Crack · Howrah" },
  { x: 78, y: 52, kind: "traffic", label: "Traffic anomaly · Salt Lake" },
  { x: 47, y: 65, kind: "mva", label: "Violation · Garia" },
  { x: 31, y: 72, kind: "road", label: "Road defect · Behala" },
  { x: 62, y: 78, kind: "traffic", label: "Congestion · Kasba" },
];

function Icon({ name, size = 21, stroke = "currentColor" }) {
  const common = { width: size, height: size, viewBox: "0 0 24 24", fill: "none", stroke, strokeWidth: 1.8, strokeLinecap: "round", strokeLinejoin: "round", "aria-hidden": true };
  const paths = {
    home: <><path d="m3 10 9-7 9 7"/><path d="M5 9v11h14V9"/><path d="M9 20v-6h6v6"/></>,
    video: <><rect x="3" y="5" width="13" height="14" rx="2"/><path d="m16 10 5-3v10l-5-3z"/></>,
    bell: <><path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9"/><path d="M10 21h4"/></>,
    map: <><path d="m3 6 6-3 6 3 6-3v15l-6 3-6-3-6 3z"/><path d="M9 3v15M15 6v15"/></>,
    chart: <><path d="M4 19V9"/><path d="M10 19V5"/><path d="M16 19v-8"/><path d="M22 19H2"/></>,
    file: <><path d="M6 3h9l4 4v14H6z"/><path d="M14 3v5h5M9 13h6M9 17h6"/></>,
    settings: <><path d="M12 15.5a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7z"/><path d="m19.4 15 .1.1 1.6 1.2-1.8 3-2-.9-.2.1a7.9 7.9 0 0 1-1.7 1l-.1.2-.3 2.1h-3.5l-.3-2.1-.2-.1a7.7 7.7 0 0 1-1.7-1l-.2-.1-2 .9-1.8-3 1.6-1.2.1-.1a8 8 0 0 1 0-2l-.1-.1-1.6-1.2 1.8-3 2 .9.2-.1a7.7 7.7 0 0 1 1.7-1l.2-.1.3-2.1h3.5l.3 2.1.1.1a7.9 7.9 0 0 1 1.7 1l.2.1 2-.9 1.8 3-1.6 1.2-.1.1a8 8 0 0 1 0 2z"/></>,
    car: <><path d="m5 17-1-5 2-5h12l2 5-1 5"/><path d="M4 12h16M7 17v2M17 17v2"/><circle cx="7" cy="15" r="1"/><circle cx="17" cy="15" r="1"/></>,
    bus: <><rect x="5" y="3" width="14" height="17" rx="3"/><path d="M5 11h14M8 16h.01M16 16h.01M8 20v2M16 20v2"/></>,
    warning: <><path d="m12 3 10 18H2L12 3z"/><path d="M12 9v5M12 17h.01"/></>,
    arrow: <><path d="M4 12h16M14 6l6 6-6 6"/></>,
    layers: <><path d="m12 3 9 5-9 5-9-5 9-5z"/><path d="m3 12 9 5 9-5M3 16l9 5 9-5"/></>,
    download: <><path d="M12 3v12M7 10l5 5 5-5M5 21h14"/></>,
    search: <><circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 5 5"/></>,
    refresh: <><path d="M20 11a8 8 0 0 0-14.7-4L3 10"/><path d="M3 5v5h5M4 13a8 8 0 0 0 14.7 4L21 14"/><path d="M21 19v-5h-5"/></>,
  };
  return <svg {...common}>{paths[name]}</svg>;
}

function StatCard({ icon, label, value, change, sub, tone }) {
  return (
    <div className={`stat-card ${tone}`}>
      <div className="stat-icon"><Icon name={icon} size={28} /></div>
      <div className="stat-copy">
        <div className="stat-label">{label}</div>
        <div className="stat-value-row"><strong>{value}</strong><span className="change">↓ {change}%</span></div>
        <div className="stat-sub">{sub}</div>
      </div>
    </div>
  );
}

function MiniChart() {
  return (
    <svg className="line-chart" viewBox="0 0 420 150" preserveAspectRatio="none">
      <defs><linearGradient id="lineFill" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor="#4e88ff" stopOpacity=".22"/><stop offset="1" stopColor="#4e88ff" stopOpacity="0"/></linearGradient></defs>
      {[20, 50, 80, 110, 140].map(y => <line key={y} x1="0" y1={y} x2="420" y2={y} stroke="#18303c" strokeWidth="1" />)}
      <path d="M0 112 C35 103 48 85 82 92 S128 80 164 94 S210 58 246 77 S292 64 330 76 S372 70 420 62 L420 150 L0 150Z" fill="url(#lineFill)" />
      <path d="M0 112 C35 103 48 85 82 92 S128 80 164 94 S210 58 246 77 S292 64 330 76 S372 70 420 62" fill="none" stroke="#5d8fff" strokeWidth="3" />
      <path d="M0 126 C40 118 66 121 100 116 S150 125 184 114 S228 110 260 118 S310 102 344 110 S390 96 420 101" fill="none" stroke="#47d69b" strokeWidth="2.5" />
      <path d="M0 138 C35 130 60 133 95 128 S146 137 180 129 S228 134 260 128 S300 137 340 129 S390 132 420 124" fill="none" stroke="#f5bd4f" strokeWidth="2.5" />
    </svg>
  );
}

function MapPanel({ selectedLayer, setSelectedLayer, onMarker }) {
  return (
    <div className="map-panel">
      <div className="map-topbar">
        <div className="map-title"><Icon name="map" size={22} stroke="#36dfcf"/><span>Live City Map</span></div>
        <select value={selectedLayer} onChange={e => setSelectedLayer(e.target.value)}>
          <option>All Layers</option><option>Road Damage</option><option>Traffic</option><option>MVA / Violation</option><option>Active Buses</option>
        </select>
      </div>
      <div className="map-canvas">
        <svg className="city-map" viewBox="0 0 900 520" preserveAspectRatio="none">
          <defs>
            <linearGradient id="river" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stopColor="#073248"/><stop offset=".5" stopColor="#0b5b72"/><stop offset="1" stopColor="#063047"/></linearGradient>
            <filter id="glow"><feGaussianBlur stdDeviation="14"/></filter>
          </defs>
          <rect width="900" height="520" fill="#091a26"/>
          <path d="M0 60 L900 0 M0 180 L900 100 M0 320 L900 230 M0 440 L900 370 M0 520 L900 470" stroke="#102d3b" strokeWidth="2"/>
          <path d="M80 0 L210 520 M250 0 L360 520 M470 0 L540 520 M680 0 L740 520 M820 0 L880 520" stroke="#102d3b" strokeWidth="2"/>
          <path d="M330 -20 C285 100 405 165 340 255 C275 345 380 400 305 545 L455 545 C510 420 425 340 495 260 C575 170 455 110 520 -20Z" fill="url(#river)" opacity=".9"/>
          <path d="M50 405 C180 340 230 370 320 325 S500 280 610 320 S760 350 900 260" fill="none" stroke="#d2a84b" strokeWidth="3" opacity=".85"/>
          <path d="M120 450 C230 390 315 420 380 350 S560 260 650 210 S790 175 890 120" fill="none" stroke="#35d9ea" strokeWidth="5" opacity=".8"/>
          <path d="M90 110 C180 150 260 145 330 190 S470 245 560 180 S720 95 840 130" fill="none" stroke="#6ad99a" strokeWidth="4" opacity=".75"/>
          {[[150,370],[255,300],[440,200],[560,315],[700,180],[780,350]].map(([x,y],i)=><circle key={i} cx={x} cy={y} r="26" fill={i%2 ? "#f33b3b" : "#ffb12b"} opacity=".18" filter="url(#glow)"/>)}
          <text x="455" y="272" fill="#d9edf7" fontSize="27" textAnchor="middle" opacity=".85">Kolkata</text>
          <text x="220" y="125" fill="#c8dce8" fontSize="15">Howrah</text>
          <text x="690" y="150" fill="#c8dce8" fontSize="15">Salt Lake</text>
          <text x="580" y="420" fill="#c8dce8" fontSize="15">Park Street</text>
          <text x="735" y="290" fill="#c8dce8" fontSize="15">New Town</text>
          <text x="150" y="455" fill="#c8dce8" fontSize="15">Behala</text>
          <text x="430" y="455" fill="#c8dce8" fontSize="15">Tollygunge</text>
        </svg>
        <div className="map-route"><Icon name="arrow" size={18}/></div>
        {mapMarkers.map((m, i) => {
          const visible = selectedLayer === "All Layers" || (selectedLayer === "Road Damage" && m.kind === "road") || (selectedLayer === "Traffic" && m.kind === "traffic") || (selectedLayer === "MVA / Violation" && m.kind === "mva");
          return visible ? <button key={i} className={`map-marker ${m.kind}`} style={{left:`${m.x}%`,top:`${m.y}%`}} onClick={() => onMarker(m)} title={m.label}><span>{m.kind === "traffic" ? <Icon name="car" size={15}/> : m.kind === "mva" ? <Icon name="warning" size={15}/> : <span className="marker-dot"/>}</span></button> : null;
        })}
        <div className="zoom"><button>+</button><button>−</button></div>
        <div className="legend">
          <div className="legend-row"><i className="blue"/>Road Damage</div>
          <div className="legend-row"><i className="green"/>Traffic Anomaly</div>
          <div className="legend-row"><i className="yellow"/>MVA / Violation</div>
          <div className="legend-row"><i className="cyan"/>Active Bus</div>
          <div className="legend-route"><span/>Bus Route</div>
          <div className="legend-title">Congestion Level</div>
          <div className="gradient-bar"/><div className="legend-scale"><span>Low</span><span>High</span></div>
        </div>
        <div className="scale">3 km</div>
        <div className="river-label">Hooghly River</div>
      </div>
    </div>
  );
}

function EventThumb({ type }) {
  return <div className={`event-thumb ${type}`}><div className="thumb-road"/><div className="thumb-vehicle"/></div>;
}

function EventCard({ event, onClick }) {
  return (
    <button className="event-card" onClick={() => onClick(event)}>
      <EventThumb type={event.thumb}/>
      <div className="event-info">
        <div className={`event-type ${event.tone}`}><span/> {event.type}</div>
        <div className="event-title">{event.title}</div>
        <div className="event-meta"><Icon name={event.tone === "yellow" ? "warning" : event.tone === "green" ? "car" : "bus"} size={12}/> {event.bus} <span>|</span> {event.place}</div>
      </div>
      <div className="event-side"><time>{event.time}</time><b className={`severity ${event.severity.toLowerCase()}`}>{event.severity}</b></div>
    </button>
  );
}

function App() {
  const [health, setHealth] = useState(null);
  const [traffic, setTraffic] = useState(null);
  const [activeNav, setActiveNav] = useState("Dashboard");
  const [selectedLayer, setSelectedLayer] = useState("All Layers");
  const [selectedEvent, setSelectedEvent] = useState(null);
  const [toast, setToast] = useState("");
  const [lastUpdated, setLastUpdated] = useState(new Date());

  const refresh = async () => {
    try {
      const h = await fetch(`${API}/api/health`).then(r => r.json());
      setHealth(h);
    } catch {
      setHealth(null);
    }
    try {
      const t = await fetch(`${API}/api/traffic/fallback`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ latitude: 22.5726, longitude: 88.3639 }) }).then(r => r.json());
      setTraffic(t);
    } catch {
      setTraffic(null);
    }
    setLastUpdated(new Date());
  };

  useEffect(() => { refresh(); const id = setInterval(refresh, 30000); return () => clearInterval(id); }, []);

  const systemOnline = health?.status === "ok";
  const congestion = traffic?.level || "MEDIUM";
  const congestionScore = traffic?.score ?? 38;
  const enabledTiers = health?.enabled_tiers?.length || 3;
  const timeLabel = useMemo(() => lastUpdated.toLocaleTimeString([], {hour:"2-digit", minute:"2-digit"}), [lastUpdated]);
  const dateLabel = useMemo(() => lastUpdated.toLocaleDateString([], {weekday:"short", day:"2-digit", month:"short", year:"numeric"}), [lastUpdated]);

  const notify = (message) => { setToast(message); window.setTimeout(() => setToast(""), 2500); };

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand"><div className="brand-mark"><span/><span/></div><div><div className="brand-name">UrbanSense</div><div className="brand-sub">AI for Safer Cities</div></div></div>
        <nav className="top-nav"><button className="active">Detect</button><button>Analyze</button><button>Act</button></nav>
        <div className="top-right"><div className="clock"><span>{dateLabel}</span><b>{timeLabel}</b></div><div className="divider"/><button className="user-chip" onClick={() => notify("UrbanSense operator console")}>U</button></div>
      </header>

      <aside className="sidebar">
        <div className="sidebar-nav">
          {["Dashboard","Live Feed","Events","Map View","Analytics","Reports","Settings"].map((item, i) => {
            const icons = ["home","video","bell","map","chart","file","settings"];
            return <button key={item} className={activeNav === item ? "selected" : ""} onClick={() => {setActiveNav(item); notify(`${item} view selected`);}}><Icon name={icons[i]} size={22}/><span>{item}</span></button>;
          })}
        </div>
        <div className="sidebar-footer"><div className="footer-line"/><span>Data for</span><strong>Cleaner Cities</strong></div>
      </aside>

      <main className="dashboard">
        <section className="stats-grid">
          <StatCard icon="map" label="Road Issues Detected" value="48" change="32" sub="vs. last week" tone="road" />
          <StatCard icon="car" label="Traffic Anomalies" value={congestion === "HIGH" ? "34" : "27"} change="18" sub="vs. last week" tone="traffic" />
          <StatCard icon="warning" label="MVA / Violations" value="16" change="24" sub="vs. last week" tone="mva" />
          <StatCard icon="bus" label="Active Buses" value="12" change="0" sub="Live on route" tone="bus" />
        </section>

        <section className="workspace">
          <MapPanel selectedLayer={selectedLayer} setSelectedLayer={setSelectedLayer} onMarker={(m) => notify(m.label)} />

          <aside className="right-column">
            <section className="feed-panel panel-card">
              <div className="section-heading"><div><Icon name="video" size={21} stroke="#39dfcc"/><h2>Live Feed <span>(Bus #07)</span></h2></div><span className="live-pill"><i/>LIVE</span></div>
              <div className="live-preview"><div className="road-scene"><div className="road-lane l1"/><div className="road-lane l2"/><div className="fake-bus"/><div className="pothole"><span>Pothole</span><b>0.92</b></div></div></div>
              <div className="feed-location"><span>Location: Park Street, Kolkata</span><b>22.5726° N, 88.3639° E</b></div>
            </section>

            <section className="events-panel panel-card">
              <div className="section-heading"><div><Icon name="file" size={21} stroke="#39dfcc"/><h2>Recent Events</h2></div><button className="view-all" onClick={() => setActiveNav("Events")}>View All</button></div>
              <div className="event-list">{demoEvents.map(event => <EventCard key={event.id} event={event} onClick={e => setSelectedEvent(e)} />)}</div>
            </section>
          </aside>
        </section>

        <section className="bottom-grid">
          <div className="panel-card distribution"><div className="section-heading"><div><Icon name="file" size={20} stroke="#39dfcc"/><h2>Event Distribution</h2></div></div><div className="donut-wrap"><div className="donut"><div><strong>91</strong><span>Total Events</span></div></div><div className="donut-legend"><div><i className="blue"/><span>Road Damage</span><b>48 (52.7%)</b></div><div><i className="green"/><span>Traffic Anomaly</span><b>27 (29.7%)</b></div><div><i className="yellow"/><span>MVA / Violation</span><b>16 (17.6%)</b></div></div></div></div>
          <div className="panel-card trend"><div className="section-heading"><div><Icon name="chart" size={20} stroke="#39dfcc"/><h2>Event Trend <span>(Last 7 Days)</span></h2></div></div><div className="chart-legend"><span><i className="blue"/>Road Damage</span><span><i className="green"/>Traffic</span><span><i className="yellow"/>MVA</span></div><MiniChart/><div className="x-axis"><span>Aug 30</span><span>Aug 31</span><span>Sep 1</span><span>Sep 2</span><span>Sep 3</span><span>Sep 4</span><span>Sep 5</span></div></div>
          <div className="panel-card issue-types"><div className="section-heading"><div><Icon name="chart" size={20} stroke="#39dfcc"/><h2>Top Issue Types</h2></div></div><div className="bars">{[["Pothole",22,"blue"],["Longitudinal Crack",14,"blue"],["Traffic Congestion",13,"green"],["No Helmet",10,"yellow"],["Signal Jump",9,"yellow"],["Wrong Way",4,"cyan"],["Alligator Crack",3,"cyan"],["Waterlogging",2,"green"]].map(([name,n,t]) => <div className="bar-row" key={name}><span>{name}</span><div><i className={t} style={{width:`${n/22*100}%`}}/></div><b>{n}</b></div>)}</div></div>
        </section>

        <section className="system-strip">
          <div><span className="sys-dot"/> <strong>System Operational</strong><small>{enabledTiers}/3 AI tiers configured</small></div>
          <div><span>Traffic Source</span><b>{traffic ? "TOMTOM FALLBACK" : "FLEET"}</b></div>
          <div><span>Congestion</span><b className={congestion.toLowerCase()}>{congestion} · {congestionScore}%</b></div>
          <button onClick={() => {refresh(); notify("Dashboard refreshed");}}><Icon name="refresh" size={16}/> Refresh</button>
        </section>
      </main>

      {selectedEvent && <div className="modal-backdrop" onClick={() => setSelectedEvent(null)}><div className="event-modal" onClick={e => e.stopPropagation()}><button className="close" onClick={() => setSelectedEvent(null)}>×</button><div className="modal-kicker">{selectedEvent.type}</div><h2>{selectedEvent.title}</h2><p>{selectedEvent.place} · {selectedEvent.bus}</p><div className="modal-grid"><div><span>Severity</span><b>{selectedEvent.severity}</b></div><div><span>Detected</span><b>{selectedEvent.time}</b></div><div><span>Source</span><b>Fleet camera</b></div><div><span>Status</span><b>Verified</b></div></div><button className="action-btn" onClick={() => {notify("Action queued for authority review"); setSelectedEvent(null);}}>Open action workflow <Icon name="arrow" size={16}/></button></div></div>}
      {toast && <div className="toast">{toast}</div>}
    </div>
  );
}

createRoot(document.getElementById("root")).render(<App />);
