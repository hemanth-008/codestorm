/**
 * Shell – app layout with top bar and navigation.
 *
 * "Drawing sheet" design: paper background, ink border, signal orange
 * accents, Bahnschrift headings, Consolas for data.
 */

import { NavLink, Outlet, useNavigate } from 'react-router-dom';
import { useFleet } from '../context/FleetProvider';
import { resetSim, getToken, clearToken } from '../api';

const NAV = [
  { to: '/', label: 'Fleet', icon: '◉' },
  { to: '/robot/R1', label: 'Detail', icon: '◎' },
  { to: '/attacks', label: 'Attacks', icon: '⚡' },
  { to: '/scorecard', label: 'Scorecard', icon: '▦' },
  { to: '/sandbox', label: 'Sandbox', icon: '△' },
  { to: '/monitor', label: 'Monitor', icon: '▤' },
  { to: '/maintenance', label: 'Maint.', icon: '⚙' },
  { to: '/login', label: 'Login', icon: '⚿' },
];

export default function Shell() {
  const { connected, frame, frameCount, clearEvents } = useFleet();
  const navigate = useNavigate();
  
  const fleetSync = frame?.fleet_sync != null ? frame.fleet_sync.toFixed(1) : '--';
  const ts = frame?.ts != null ? frame.ts.toFixed(1) : '--';
  
  // Waking up heuristic: not connected and no frames received yet (or mock is off and it's trying to connect)
  const isWakingUp = !connected && frameCount === 0;

  const handleReset = async () => {
    if (!confirm('Are you sure you want to reset the simulation?')) return;
    try {
      await resetSim();
      clearEvents();
    } catch (e) {
      console.error(e);
      alert('Failed to reset: ' + e.message);
    }
  };

  let isOperator = true;

  let role = null;
  const token = getToken();
  if (token) {
    try {
      const payload = JSON.parse(atob(token.split('.')[1]));
      role = payload.role;
      isOperator = role === 'operator';
    } catch { }
  }

  const handleLogout = () => {
    clearToken();
    navigate('/');
  };

  const navItems = NAV.filter(n => n.to !== '/login' || !token);

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
        <div className="status" style={{ display: 'flex', alignItems: 'center' }}>
          {isOperator && (
            <button className="btn" style={{ marginRight: 16, padding: '4px 8px', fontSize: 11, fontWeight: 'bold', borderColor: 'var(--signal)', color: 'var(--signal)' }} onClick={handleReset}>
              RESET SCENARIO
            </button>
          )}
          <span className="mono-sm" style={{ marginRight: 12 }}>
            T={ts}s &nbsp; sync={fleetSync}
          </span>
          <span className={connected ? 'dot live' : 'dot'} />
          {connected ? 'Live' : 'Offline'}
        </div>
      </header>

      {/* ── Navigation ────────────────────────────── */}
      <nav className="nav-bar">
        {navItems.map(({ to, label, icon }) => (
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
        {token && (
          <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 12 }}>
            <span className="mono-sm" style={{ fontWeight: 'bold' }}>
              ROLE: {role.toUpperCase()}
            </span>
            <button className="nav-link" onClick={handleLogout} style={{ background: 'transparent', border: 'none', cursor: 'pointer' }}>
              LOGOUT
            </button>
          </div>
        )}
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

