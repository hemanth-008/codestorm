/**
 * RobotDetail (Task C3)
 *
 * Shows detailed twin-vs-real data for a single robot:
 * TwinCharts, HealthGauge, and DecisionPanel.
 */
import { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { useFleet } from '../context/FleetProvider';
import { postOverride } from '../api';
import TwinCharts from '../components/TwinCharts';
import HealthGauge from '../components/HealthGauge';
import DecisionPanel from '../components/DecisionPanel';

const ROBOT_IDS = ['R1', 'D1', 'G1'];

export default function RobotDetail() {
  const { id } = useParams();
  const { frame } = useFleet();
  const [history, setHistory] = useState({});

  useEffect(() => {
    if (!frame) return;
    setHistory((prev) => {
      const next = { ...prev };
      for (const r of frame.robots) {
        const h = next[r.robot_id] || [];
        const point = {
          t: r.ts,
          residual_pos: r.twin.residual_pos,
          est_battery: r.twin.est.battery,
          pred_battery: r.twin.pred.battery,
          est_temp: r.twin.est.motor_temp,
          pred_temp: r.twin.pred.motor_temp,
          est_vib: r.twin.est.vibration,
          pred_vib: r.twin.pred.vibration,
        };
        next[r.robot_id] = [...h, point].slice(-60); // Keep last 12s at 5Hz
      }
      return next;
    });
  }, [frame]);

  const robot = frame?.robots?.find((r) => r.robot_id === id);

  const handleOverride = async (action, reason) => {
    if (!id) return;
    try {
      await postOverride({ robot_id: id, action, reason });
    } catch (e) {
      console.error('Failed to post override', e);
    }
  };

  return (
    <div>
      <div className="btn-row" style={{ marginBottom: 14 }}>
        {ROBOT_IDS.map((rid) => (
          <Link
            key={rid}
            to={`/robot/${rid}`}
            className={`btn${rid === id ? ' btn-active' : ''}`}
            style={{ textDecoration: 'none', padding: '6px 16px', fontSize: 14 }}
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
        <div style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
          
          <div className="panel">
            <div className="panel-head">
              <span>{robot.name} — Twin Telemetry Analysis</span>
              <span className="tag">{robot.twin.mode}</span>
            </div>
            <div className="panel-body">
              <TwinCharts history={history[id]} />
            </div>
          </div>

          <div className="panels">
            <div className="panel">
              <div className="panel-head">
                <span>Health & Diagnostics</span>
                <span className="tag">Wear Estimator</span>
              </div>
              <div className="panel-body">
                <HealthGauge health={robot.health} />
              </div>
            </div>

            <div className="panel">
              <div className="panel-head">
                <span>Decision Engine</span>
                <span className="tag">{robot.twin.sync_score.toFixed(0)} sync</span>
              </div>
              <div className="panel-body">
                <DecisionPanel decision={robot.decision} onOverride={handleOverride} />
              </div>
            </div>
          </div>
          
        </div>
      )}
    </div>
  );
}
