import { Link } from 'react-router-dom';

/**
 * RobotCard - displays status for a single robot on the overview page.
 * Includes sync bar, battery, mode badge, and health/RUL badge.
 */
export default function RobotCard({ robot }) {
  const { twin, telemetry, health, name, robot_type, robot_id } = robot;
  const isHealthy = health.health_index > 0.7;
  const healthClass = isHealthy ? '' : ' warn';

  return (
    <div className="panel">
      <div className="panel-head">
        <span>{name} ({robot_type})</span>
        <Link to={`/robot/${robot_id}`} className="tag" style={{ textDecoration: 'none' }}>
          Details →
        </Link>
      </div>
      <div className="panel-body">
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 12 }}>
          <div>
            <div className="kpi-label">Twin Mode</div>
            <div className={`action-badge ${twin.mode !== 'synced' ? 'warn' : ''}`} style={{ fontSize: 14 }}>
              {twin.mode}
            </div>
          </div>
          <div style={{ textAlign: 'right' }}>
            <div className="kpi-label">Health</div>
            <div className={`action-badge${healthClass}`} style={{ fontSize: 14 }}>
              {health.status.toUpperCase()} 
              {health.rul_s != null && ` (${health.rul_s.toFixed(0)}s RUL)`}
            </div>
          </div>
        </div>

        <div className="kpi-label">Sync Score: {twin.sync_score.toFixed(0)}</div>
        <div className="sync-bar-wrap" style={{ margin: '6px 0 14px' }}>
          <div 
            className="sync-bar-fill" 
            style={{ 
              width: `${Math.max(0, Math.min(100, twin.sync_score))}%`,
              background: twin.sync_score > 80 ? 'var(--ink)' : 'var(--signal)'
            }} 
          />
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
          <div>
            <div className="kpi-label">Battery</div>
            <div className="mono-sm" style={{ fontSize: 14 }}>
              <span style={{ color: telemetry.battery < 30 ? 'var(--signal)' : 'inherit', fontWeight: 'bold' }}>
                {telemetry.battery.toFixed(0)}%
              </span>
            </div>
          </div>
          <div>
            <div className="kpi-label">Speed</div>
            <div className="mono-sm" style={{ fontSize: 14 }}>{telemetry.speed.toFixed(1)} m/s</div>
          </div>
        </div>
      </div>
    </div>
  );
}
