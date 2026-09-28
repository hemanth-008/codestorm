import { useState, useEffect, useRef } from "react";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid,
  ResponsiveContainer, Tooltip,
} from "recharts";

const API = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";
const WAYPOINTS = [[10, 10], [90, 10], [90, 50], [50, 50], [50, 90], [10, 90]];
const MAX_POINTS = 30;

const stamp = (t) =>
  new Date(t * 1000).toLocaleTimeString([], { hour12: false });

function Spark({ data, dataKey, color, domain }) {
  return (
    <ResponsiveContainer width="100%" height={170}>
      <LineChart data={data} margin={{ top: 6, right: 8, bottom: 0, left: 0 }}>
        <CartesianGrid stroke="#CFCABB" strokeDasharray="3 3" />
        <XAxis dataKey="t" hide />
        <YAxis
          domain={domain}
          width={36}
          stroke="#161616"
          tick={{ fontSize: 11, fontFamily: "Consolas" }}
        />
        <Tooltip
          contentStyle={{
            background: "#F8F6EE",
            border: "1px solid #161616",
            borderRadius: 0,
            fontFamily: "Consolas",
            fontSize: 12,
          }}
        />
        <Line
          type="monotone"
          dataKey={dataKey}
          stroke={color}
          strokeWidth={2}
          dot={false}
          isAnimationActive={false}
        />
      </LineChart>
    </ResponsiveContainer>
  );
}

function RobotMap({ data, trail }) {
  const route = WAYPOINTS.map((p) => p.join(",")).join(" ");
  const rad = data ? (data.heading * Math.PI) / 180 : 0;
  return (
    <svg className="map-svg" viewBox="0 0 100 100">
      {[...Array(11)].map((_, i) => (
        <g key={i}>
          <line x1={i * 10} y1="0" x2={i * 10} y2="100" stroke="#CFCABB" strokeWidth="0.3" />
          <line x1="0" y1={i * 10} x2="100" y2={i * 10} stroke="#CFCABB" strokeWidth="0.3" />
        </g>
      ))}
      <polygon
        points={route}
        fill="none"
        stroke="#161616"
        strokeWidth="0.5"
        strokeDasharray="1.5 1.5"
      />
      {WAYPOINTS.map(([x, y], i) => (
        <g key={i}>
          <rect x={x - 1.5} y={y - 1.5} width="3" height="3" fill="#F1EEE4" stroke="#161616" strokeWidth="0.4" />
          <text x={x + 2.5} y={y - 2} fontSize="3.2" fontFamily="Consolas" fill="#161616">
            WP{i + 1}
          </text>
        </g>
      ))}
      {trail.length > 1 && (
        <polyline
          points={trail.map((p) => p.join(",")).join(" ")}
          fill="none"
          stroke="#FF5A1F"
          strokeWidth="0.9"
        />
      )}
      {data && (
        <g>
          <line
            x1={data.x}
            y1={data.y}
            x2={data.x + 6 * Math.cos(rad)}
            y2={data.y + 6 * Math.sin(rad)}
            stroke="#161616"
            strokeWidth="0.7"
          />
          <circle cx={data.x} cy={data.y} r="2.2" fill="#FF5A1F" stroke="#161616" strokeWidth="0.5" />
        </g>
      )}
    </svg>
  );
}

export default function App() {
  const [data, setData] = useState(null);
  const [history, setHistory] = useState([]);
  const [trail, setTrail] = useState([]);
  const [log, setLog] = useState([]);
  const [online, setOnline] = useState(false);
  const lastStatus = useRef(null);

  useEffect(() => {
    let cancelled = false;
    const tick = async () => {
      try {
        const res = await fetch(`${API}/api/telemetry`);
        const d = await res.json();
        if (cancelled) return;
        setData(d);
        setOnline(true);
        setHistory((h) =>
          [...h, { t: stamp(d.time), speed: d.speed, battery: d.battery }].slice(-MAX_POINTS)
        );
        setTrail((tr) => [...tr, [d.x, d.y]].slice(-40));
        if (lastStatus.current !== d.status) {
          const warn = d.status === "LOW BATTERY";
          setLog((l) =>
            [
              {
                t: stamp(d.time),
                m: warn ? "Battery below 30% - return to dock" : "Navigating patrol route",
                warn,
              },
              ...l,
            ].slice(0, 20)
          );
          lastStatus.current = d.status;
        }
      } catch {
        if (!cancelled) setOnline(false);
      }
    };
    tick();
    const id = setInterval(tick, 1000);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, []);

  const low = data && data.battery < 30;

  return (
    <div className="sheet">
      <div className="topbar">
        <div className="title-row">
          <div className="sheetno">01</div>
          <div>
            <h1>Robot Dashboard</h1>
            <div className="sub">Robotics &amp; Autonomous Systems // Live telemetry</div>
          </div>
        </div>
        <div className="status">
          <span className={online ? "dot live" : "dot"} />
          {online ? "Live" : "Backend offline"}
        </div>
      </div>

      <div className="kpis">
        <div className="kpi">
          <div className="kpi-label">Position (x, y)</div>
          <div className="kpi-value">
            {data ? `${data.x.toFixed(1)}, ${data.y.toFixed(1)}` : "--"}
          </div>
        </div>
        <div className={low ? "kpi alert" : "kpi"}>
          <div className="kpi-label">Battery</div>
          <div className="kpi-value">
            {data ? data.battery.toFixed(0) : "--"}
            <span className="kpi-unit">%</span>
          </div>
        </div>
        <div className="kpi">
          <div className="kpi-label">Speed</div>
          <div className="kpi-value">
            {data ? data.speed.toFixed(2) : "--"}
            <span className="kpi-unit">m/s</span>
          </div>
        </div>
        <div className={low ? "kpi alert" : "kpi"}>
          <div className="kpi-label">State</div>
          <div className="kpi-value" style={{ fontSize: 22, paddingTop: 8 }}>
            {data ? data.status : "--"}
          </div>
        </div>
      </div>

      <div className="panels">
        <div className="panel">
          <div className="panel-head">
            <span>Fig. 01 - Patrol map</span>
            <span className="tag">100 x 100</span>
          </div>
          <div className="panel-body">
            <RobotMap data={data} trail={trail} />
          </div>
        </div>

        <div className="panel">
          <div className="panel-head">
            <span>Fig. 02 - Battery / speed</span>
            <span className="tag">30 s</span>
          </div>
          <div className="panel-body">
            <div className="kpi-label">Battery %</div>
            <Spark data={history} dataKey="battery" color="#FF5A1F" domain={[0, 100]} />
            <div className="kpi-label" style={{ marginTop: 10 }}>Speed m/s</div>
            <Spark data={history} dataKey="speed" color="#161616" domain={[0, 2]} />
          </div>
        </div>
      </div>

      <div className="panel">
        <div className="panel-head">
          <span>Event log</span>
          <span className="tag">{log.length} events</span>
        </div>
        <div className="log">
          {log.length === 0 && <div className="log-empty">Waiting for events...</div>}
          {log.map((e, i) => (
            <div key={i} className={e.warn ? "log-row warn" : "log-row"}>
              <span className="t">{e.t}</span>
              <span className="m">{e.m}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}