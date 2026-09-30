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
];

export default function Shell() {
  const { connected, frame } = useFleet();
  const fleetSync = frame ? frame.fleet_sync.toFixed(1) : '--';
  const ts = frame ? frame.ts.toFixed(1) : '--';

  return (
    <div className="sheet">
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
