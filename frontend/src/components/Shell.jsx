/**
 * Shell – app layout with top bar and navigation.
 *
 * "Drawing sheet" design: paper background, ink border, signal orange
 * accents, Bahnschrift headings, Consolas for data.
 */

import { NavLink, Outlet } from 'react-router-dom';
import { useFleet } from '../context/FleetProvider';

const NAV = [
  { to: '/', label: 'Fleet', icon: '◉' },
  { to: '/robot/R1', label: 'Detail', icon: '◎' },
  { to: '/attacks', label: 'Attacks', icon: '⚡' },
  { to: '/scorecard', label: 'Scorecard', icon: '▦' },
  { to: '/sandbox', label: 'Sandbox', icon: '△' },
  { to: '/monitor', label: 'Monitor', icon: '▤' },
  { to: '/login', label: 'Login', icon: '⚿' },
];

export default function Shell() {
  const { connected, frame, frameCount } = useFleet();
  const fleetSync = frame?.fleet_sync != null ? frame.fleet_sync.toFixed(1) : '--';
  const ts = frame?.ts != null ? frame.ts.toFixed(1) : '--';
  
  // Waking up heuristic: not connected and no frames received yet (or mock is off and it's trying to connect)
  const isWakingUp = !connected && frameCount === 0;

  return (
    <div className="sheet">
      {isWakingUp && (
        <div style={{ background: 'var(--signal)', color: 'var(--paper)', padding: '8px 16px', textAlign: 'center', fontWeight: 'bold', fontSize: 14, marginBottom: 18, fontFamily: 'var(--mono)' }}>
          Backend is waking up (Render free tier). This may take up to 50 seconds...
        </div>
      )}

      {/* ── Top bar ───────────────────────────────── */}
      <header className="topbar">
        <div className="title-row">
          <div className="sheetno">FT</div>
          <div>
            <h1>FleetTwin</h1>
            <div className="sub">Digital Twin // Fleet Ops Dashboard</div>
          </div>
        </div>
        <div className="status">
          <span className="mono-sm" style={{ marginRight: 12 }}>
            T={ts}s &nbsp; sync={fleetSync}
          </span>
          <span className={connected ? 'dot live' : 'dot'} />
          {connected ? 'Live' : 'Offline'}
        </div>
      </header>

      {/* ── Navigation ────────────────────────────── */}
      <nav className="nav-bar">
        {NAV.map(({ to, label, icon }) => (
          <NavLink
            key={to}
            to={to}
            end={to === '/'}
            className={({ isActive }) => `nav-link${isActive ? ' active' : ''}`}
          >
            <span className="nav-icon">{icon}</span>
            {label}
          </NavLink>
        ))}
      </nav>

      {/* ── Page content ──────────────────────────── */}
      <main className="page-content">
        <Outlet />
      </main>

      {/* ── Footer ────────────────────────────────── */}
      <footer className="sheet-footer">
        <span>FleetTwin v0.1</span>
        <span className="mono-sm">
          {connected ? `${frame?.robots?.length || 0} robots | ${frame?.ingest?.msgs_per_s?.toFixed(0) || 0} msg/s` : 'disconnected'}
        </span>
      </footer>
    </div>
  );
}
