/**
 * Maintenance page (Eval 4, item 2)
 *
 * Top section: model-based lifetime and maintenance interval per robot type.
 * Bottom section: filterable log of maintenance-related events per robot
 * (maintenance_due, health_warning, and relevant critical events).
 */
import { useState, useMemo } from 'react';
import { useFleet } from '../context/FleetProvider';

// Model-based estimates from physics.py wear rates.
// Wear rises linearly; defaults: R1 ~12 min, D1 ~15 min, G1 ~20 min.
const TYPE_INFO = [
  {
    type: 'rover',
    label: 'Rover',
    id: 'R1',
    icon: '◉',
    lifetime: '~12 min',
    lifetimeSec: 720,
    interval: '~6 min',
    intervalSec: 360,
    desc: 'High wear rate from ground friction and terrain. Maintenance triggered at health index < 0.4.',
  },
  {
    type: 'drone',
    label: 'Drone',
    id: 'D1',
    icon: '◎',
    lifetime: '~15 min',
    lifetimeSec: 900,
    interval: '~8 min',
    intervalSec: 480,
    desc: 'Moderate wear from rotor stress and wind loading. Battery drain is highest among fleet.',
  },
  {
    type: 'agv',
    label: 'AGV',
    id: 'G1',
    icon: '▦',
    lifetime: '~20 min',
    lifetimeSec: 1200,
    interval: '~10 min',
    intervalSec: 600,
    desc: 'Lowest wear rate on flat surfaces. Limited yaw rate preserves mechanical components.',
  },
];

const MAINT_KINDS = new Set([
  'maintenance_due',
  'health_warning',
  'recharge',
]);

/** Severity badge color map */
function severityStyle(sev) {
  switch (sev) {
    case 'critical': return { background: 'var(--signal)', color: 'var(--paper)', fontWeight: 700 };
    case 'warn': return { background: 'var(--ink)', color: 'var(--paper)' };
    default: return { background: 'var(--grid)', color: 'var(--ink)' };
  }
}

/** Format sim seconds into human readable */
function fmtTime(ts) {
  if (ts == null) return '--';
  const m = Math.floor(ts / 60);
  const s = (ts % 60).toFixed(1);
  return m > 0 ? `${m}m ${s}s` : `${s}s`;
}

export default function Maintenance() {
  const { frame, events } = useFleet();
  const [filter, setFilter] = useState('ALL');

  // Current health data per robot from the live frame
  const robotHealth = useMemo(() => {
    if (!frame?.robots) return {};
    const map = {};
    for (const r of frame.robots) {
      map[r.robot_id] = r.health;
    }
    return map;
  }, [frame]);

  // Filter maintenance-related events
  const maintEvents = useMemo(() => {
    return events
      .filter((e) => MAINT_KINDS.has(e.kind))
      .filter((e) => filter === 'ALL' || e.robot_id === filter);
  }, [events, filter]);

  return (
    <div>
      {/* ── Model-Based Estimates ─────────────────── */}
      <div className="panel" style={{ marginBottom: 18 }}>
        <div className="panel-head">
          <span>Robot Type Lifecycle — Model-Based Estimates</span>
          <span className="tag">Physics Model</span>
        </div>
        <div className="panel-body">
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: 16 }}>
            {TYPE_INFO.map((info) => {
              const h = robotHealth[info.id];
              const healthIdx = h?.health_index ?? null;
              const rul = h?.rul_s ?? null;
              const status = h?.status ?? 'ok';

              return (
                <div
                  key={info.type}
                  style={{
                    border: '1.5px solid var(--ink)',
                    background: 'var(--paper)',
                    padding: 16,
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                      <span style={{ fontSize: 24 }}>{info.icon}</span>
                      <div>
                        <div style={{ fontWeight: 700, fontSize: 18 }}>{info.label}</div>
                        <span className="mono-sm">{info.id}</span>
                      </div>
                    </div>
                    <span
                      style={{
                        ...severityStyle(status === 'critical' ? 'critical' : status === 'maintenance' ? 'warn' : 'info'),
                        padding: '3px 8px',
                        fontFamily: 'var(--mono)',
                        fontSize: 11,
                        textTransform: 'uppercase',
                        letterSpacing: '0.04em',
                      }}
                    >
                      {status}
                    </span>
                  </div>

                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginBottom: 10 }}>
                    <div>
                      <div className="kpi-label">Typical Lifetime</div>
                      <div style={{ fontFamily: 'var(--mono)', fontSize: 20, fontWeight: 700, marginTop: 2 }}>
                        {info.lifetime}
                      </div>
                    </div>
                    <div>
                      <div className="kpi-label">Maint. Interval</div>
                      <div style={{ fontFamily: 'var(--mono)', fontSize: 20, fontWeight: 700, marginTop: 2 }}>
                        {info.interval}
                      </div>
                    </div>
                  </div>

                  {healthIdx != null && (
                    <div style={{ marginBottom: 8 }}>
                      <div className="kpi-label" style={{ marginBottom: 4 }}>
                        Current Health: {(healthIdx * 100).toFixed(0)}% — RUL: {fmtTime(rul)}
                      </div>
                      <div style={{ height: 8, background: 'var(--paper)', border: '1px solid var(--ink)', position: 'relative' }}>
                        <div
                          style={{
                            height: '100%',
                            width: `${Math.max(0, Math.min(100, healthIdx * 100))}%`,
                            background: healthIdx > 0.5 ? 'var(--ink)' : 'var(--signal)',
                            transition: 'width 0.4s ease-out',
                          }}
                        />
                      </div>
                    </div>
                  )}

                  <div style={{ fontSize: 13, color: 'var(--muted)', lineHeight: 1.4 }}>
                    {info.desc}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {/* ── Maintenance Event Log ─────────────────── */}
      <div className="panel">
        <div className="panel-head">
          <span>Maintenance Event Log</span>
          <span className="tag">{maintEvents.length} events</span>
        </div>
        <div className="panel-body">
          {/* Filter buttons */}
          <div className="btn-row" style={{ marginBottom: 12 }}>
            {['ALL', 'R1', 'D1', 'G1'].map((f) => (
              <button
                key={f}
                className={`btn${filter === f ? ' btn-active' : ''}`}
                onClick={() => setFilter(f)}
                style={{ padding: '4px 12px', fontSize: 12 }}
              >
                {f}
              </button>
            ))}
          </div>

          {maintEvents.length === 0 ? (
            <div className="log-empty">No maintenance events recorded yet.</div>
          ) : (
            <div style={{ maxHeight: 340, overflowY: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontFamily: 'var(--mono)', fontSize: 13 }}>
                <thead>
                  <tr style={{ borderBottom: '1.5px solid var(--ink)', textTransform: 'uppercase', fontSize: 11, letterSpacing: '0.04em', color: 'var(--muted)' }}>
                    <th style={{ textAlign: 'left', padding: '6px 8px' }}>Time</th>
                    <th style={{ textAlign: 'left', padding: '6px 8px' }}>Robot</th>
                    <th style={{ textAlign: 'left', padding: '6px 8px' }}>Severity</th>
                    <th style={{ textAlign: 'left', padding: '6px 8px' }}>Reason</th>
                  </tr>
                </thead>
                <tbody>
                  {maintEvents.map((evt) => (
                    <tr key={evt.id} style={{ borderBottom: '1px dashed var(--grid)' }}>
                      <td style={{ padding: '6px 8px', whiteSpace: 'nowrap' }}>
                        {fmtTime(evt.ts)}
                      </td>
                      <td style={{ padding: '6px 8px', fontWeight: 700 }}>
                        {evt.robot_id || '—'}
                      </td>
                      <td style={{ padding: '6px 8px' }}>
                        <span
                          style={{
                            ...severityStyle(evt.severity),
                            padding: '2px 6px',
                            fontSize: 10,
                            textTransform: 'uppercase',
                            letterSpacing: '0.04em',
                          }}
                        >
                          {evt.severity}
                        </span>
                      </td>
                      <td style={{ padding: '6px 8px' }}>
                        {evt.message}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
