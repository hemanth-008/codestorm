/**
 * RobotDetail – placeholder for C3.
 *
 * Shows detailed twin-vs-real data for a single robot.
 * Full charts, health gauge, and decision panel come in C3.
 */

import { useParams, Link } from 'react-router-dom';
import { useFleet } from '../context/FleetProvider';

const ROBOT_IDS = ['R1', 'D1', 'G1'];

export default function RobotDetail() {
  const { id } = useParams();
  const { frame } = useFleet();

  const robot = frame?.robots?.find((r) => r.robot_id === id);

  return (
    <div>
      {/* Robot selector tabs */}
      <div className="btn-row" style={{ marginBottom: 14 }}>
        {ROBOT_IDS.map((rid) => (
          <Link
            key={rid}
            to={`/robot/${rid}`}
            className={`btn${rid === id ? ' btn-active' : ''}`}
          >
            {rid}
          </Link>
        ))}
      </div>

      {!robot ? (
        <div className="empty-state">
          {frame ? `Robot ${id} not found in stream` : 'Waiting for stream data…'}
        </div>
      ) : (
        <div className="panels">
          <div className="panel">
            <div className="panel-head">
              <span>{robot.name} — Twin State</span>
              <span className="tag">{robot.twin.mode}</span>
            </div>
            <div className="panel-body">
              <div className="kpi-label">Position</div>
              <div className="mono-sm">
                x={robot.twin.est.x.toFixed(1)} y={robot.twin.est.y.toFixed(1)}
              </div>
              <div className="kpi-label" style={{ marginTop: 10 }}>Residual</div>
              <div className="mono-sm">{robot.twin.residual_pos.toFixed(3)} m</div>
              <div className="kpi-label" style={{ marginTop: 10 }}>Sync Score</div>
              <div className="kpi-value" style={{ fontSize: 28 }}>
                {robot.twin.sync_score.toFixed(1)}
              </div>
            </div>
          </div>

          <div className="panel">
            <div className="panel-head">
              <span>Health</span>
              <span className="tag">{robot.health.status}</span>
            </div>
            <div className="panel-body">
              <div className="kpi-label">Health Index</div>
              <div className="kpi-value" style={{ fontSize: 28 }}>
                {(robot.health.health_index * 100).toFixed(0)}%
              </div>
              <div className="kpi-label" style={{ marginTop: 10 }}>RUL</div>
              <div className="mono-sm">
                {robot.health.rul_s != null ? `${robot.health.rul_s.toFixed(0)}s` : '—'}
              </div>
              <div className="kpi-label" style={{ marginTop: 10 }}>Decision</div>
              <div className="action-badge">
                {robot.decision.action.replace(/_/g, ' ')}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
