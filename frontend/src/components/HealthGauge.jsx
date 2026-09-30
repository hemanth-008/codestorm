/**
 * HealthGauge - Visual representation of Health Index and RUL.
 */
export default function HealthGauge({ health }) {
  if (!health) return null;
  const hi = Math.max(0, Math.min(1, health.health_index));
  const hue = hi > 0.7 ? 120 : hi > 0.4 ? 40 : 0;
  
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <div>
        <div className="kpi-label">Health Index</div>
        <div style={{ display: 'flex', alignItems: 'flex-end', gap: 12 }}>
          <div className="kpi-value" style={{ fontSize: 36, color: `hsl(${hue}, 80%, 40%)` }}>
            {(hi * 100).toFixed(0)}<span className="kpi-unit">%</span>
          </div>
          <div className="action-badge" style={{ marginBottom: 4 }}>
            {health.status.toUpperCase()}
          </div>
        </div>
      </div>
      
      <div>
        <div className="kpi-label">RUL (Remaining Useful Life)</div>
        {health.rul_s != null ? (
          <div>
            <div className="kpi-value" style={{ fontSize: 24 }}>
              {health.rul_s.toFixed(0)}<span className="kpi-unit">s</span>
            </div>
            {health.rul_low_s != null && health.rul_high_s != null && (
              <div className="mono-sm" style={{ marginTop: 4 }}>
                range: {health.rul_low_s.toFixed(0)}s – {health.rul_high_s.toFixed(0)}s
              </div>
            )}
          </div>
        ) : (
          <div className="mono-sm">No RUL estimate available</div>
        )}
      </div>

      <div>
        <div className="kpi-label">Drivers</div>
        <div className="mono-sm" style={{ marginTop: 4 }}>
          {Object.entries(health.drivers || {}).map(([k, v]) => (
            <span key={k} style={{ display: 'inline-block', width: '50%' }}>
              {k}: {v.toFixed(2)}
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}
