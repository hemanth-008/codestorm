/**
 * Maintenance page (Eval 4, item 2)
 *
 * Top section: model-based lifetime and maintenance interval per robot type.
 *   - When connected to real backend, fetched from GET /api/maintenance/lifetime-reference
 *   - Falls back to hardcoded estimates from physics.py wear rates
 * Bottom section: filterable log of maintenance-related events per robot.
 *   - When connected to real backend, fetched from GET /api/maintenance/log
 *   - Falls back to stream events filtered for maintenance kinds
 */
import { useState, useMemo, useEffect } from 'react';
import { useFleet } from '../context/FleetProvider';
import { getMaintenanceLog, getLifetimeReference } from '../api';

const USE_MOCK = import.meta.env.VITE_USE_MOCK !== '0';

// Fallback model-based estimates from physics.py wear rates.
// Wear rises linearly; defaults: R1 ~12 min, D1 ~15 min, G1 ~20 min.
const FALLBACK_TYPE_INFO = [
  {
    type: 'rover',
    label: 'Rover',
    id: 'R1',
    icon: '◉',
    lifetime: '~40 min',
    interval: '~22 min',
    desc: 'High wear rate from ground friction and terrain. Maintenance triggered at health index < 0.4.',
  },
  {
    type: 'drone',
    label: 'Drone',
    id: 'D1',
    icon: '◎',
    lifetime: '~80 min',
    interval: '~44 min',
    desc: 'Moderate wear from rotor stress and wind loading. Battery drain is highest among fleet.',
  },
  {
    type: 'agv',
    label: 'AGV',
    id: 'G1',
    icon: '▦',
    lifetime: '~100 min',
    interval: '~55 min',
    desc: 'Lowest wear rate on flat surfaces. Limited yaw rate preserves mechanical components.',
  },
];

const TYPE_TO_ID = { rover: 'R1', drone: 'D1', agv: 'G1' };
const TYPE_ICONS = { rover: '◉', drone: '◎', agv: '▦' };
const TYPE_LABELS = { rover: 'Rover', drone: 'Drone', agv: 'AGV' };
const TYPE_DESCS = {
  rover: 'High wear rate from ground friction and terrain. Maintenance triggered at health index < 0.4.',
  drone: 'Moderate wear from rotor stress and wind loading. Battery drain is highest among fleet.',
  agv: 'Lowest wear rate on flat surfaces. Limited yaw rate preserves mechanical components.',
};

const MAINT_KINDS = new Set([
  'maintenance_due',
  'health_warning',
  'health_critical',
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
  const [backendLog, setBackendLog] = useState(null);
  const [lifetimeRef, setLifetimeRef] = useState(null);
  const [fetchError, setFetchError] = useState(null);

  // Fetch real data from backend when not in mock mode
  useEffect(() => {
    if (USE_MOCK) return;

    let cancelled = false;
    const fetchData = async () => {
      try {
        const [log, ref] = await Promise.all([
          getMaintenanceLog(),
          getLifetimeReference(),
        ]);
        if (!cancelled) {
          setBackendLog(log);
          setLifetimeRef(ref);
          setFetchError(null);
        }
      } catch (err) {
        if (!cancelled) setFetchError(err.message);
      }
    };
    fetchData();
    // Refresh every 10s
    const interval = setInterval(fetchData, 10000);
    return () => { cancelled = true; clearInterval(interval); };
  }, []);

  // Build type info from backend lifetime-reference or fallback
  const typeInfo = useMemo(() => {
    if (lifetimeRef && lifetimeRef.length > 0) {
      return lifetimeRef.map((r) => ({
        type: r.robot_type,
        label: TYPE_LABELS[r.robot_type] || r.robot_type,
        id: TYPE_TO_ID[r.robot_type] || r.robot_type.toUpperCase()[0] + '1',
        icon: TYPE_ICONS[r.robot_type] || '◉',
        lifetime: `~${r.typical_operating_duration_mins} min`,
        interval: `~${r.suggested_maintenance_interval_mins} min`,
        desc: r.note || TYPE_DESCS[r.robot_type] || r.common_failure_reasons || '',
      }));
    }
    return FALLBACK_TYPE_INFO;
  }, [lifetimeRef]);

  // Current health data per robot from the live frame
  const robotHealth = useMemo(() => {
    if (!frame?.robots) return {};
    const map = {};
    for (const r of frame.robots) {
      map[r.robot_id] = r.health;
    }
    return map;
  }, [frame]);

  // Maintenance events: use backend log or fall back to stream events
  const maintEvents = useMemo(() => {
    if (backendLog) {
      return backendLog
        .filter((e) => filter === 'ALL' || e.robot_id === filter);
    }
    // Fallback: filter stream events
    return events
      .filter((e) => MAINT_KINDS.has(e.kind))
      .filter((e) => filter === 'ALL' || e.robot_id === filter);
  }, [backendLog, events, filter]);

  const isBackendData = backendLog != null;

  return (
    <div>
      {fetchError && (
        <div className="mono-sm" style={{ color: 'var(--signal)', marginBottom: 12 }}>
          ⚠ Could not fetch maintenance data: {fetchError}. Showing stream events.
        </div>
      )}

      {/* ── Model-Based Estimates ─────────────────── */}
      <div className="panel" style={{ marginBottom: 18 }}>
        <div className="panel-head">
          <span>Robot Type Lifecycle — Model-Based Estimates</span>
          <span className="tag">{isBackendData ? 'Live Backend' : 'Physics Model'}</span>
        </div>
        <div className="panel-body">
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: 16 }}>
            {typeInfo.map((info) => {
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
                    {isBackendData && (
                      <th style={{ textAlign: 'left', padding: '6px 8px' }}>Action</th>
                    )}
                  </tr>
                </thead>
                <tbody>
                  {maintEvents.map((evt, idx) => (
                    <tr key={evt.id || `log-${idx}`} style={{ borderBottom: '1px dashed var(--grid)' }}>
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
                        {/* Backend log has plain_language_reason; stream events have message */}
                        {evt.plain_language_reason || evt.message}
                      </td>
                      {isBackendData && (
                        <td style={{ padding: '6px 8px', fontSize: 11, color: 'var(--muted)' }}>
                          {evt.recommended_action || '—'}
                        </td>
                      )}
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
