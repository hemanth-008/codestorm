/**
 * FleetOverview – placeholder for C2.
 *
 * Shows a brief status grid for all robots from the stream.
 * Full implementation with arena map, trails, and robot cards comes in C2.
 */

import { useFleet } from '../context/FleetProvider';

export default function FleetOverview() {
  const { frame } = useFleet();

  if (!frame) {
    return <div className="empty-state">Waiting for stream data…</div>;
  }

  return (
    <div>
      <div className="panel-head" style={{ marginBottom: 12 }}>
        <span>Fleet Overview</span>
        <span className="tag">{frame.robots.length} robots</span>
      </div>

      <div className="kpis" style={{ gridTemplateColumns: `repeat(${frame.robots.length}, 1fr)` }}>
        {frame.robots.map((r) => (
          <div key={r.robot_id} className="kpi">
            <div className="kpi-label">{r.name} ({r.robot_type})</div>
            <div className="kpi-value" style={{ fontSize: 22 }}>
              {r.twin.sync_score.toFixed(0)}
              <span className="kpi-unit">sync</span>
            </div>
            <div className="mono-sm" style={{ marginTop: 6 }}>
              bat {r.telemetry.battery.toFixed(0)}% &nbsp;
              spd {r.telemetry.speed.toFixed(1)} m/s &nbsp;
              hp {(r.health.health_index * 100).toFixed(0)}%
            </div>
          </div>
        ))}
      </div>

      <div className="panel" style={{ marginTop: 18 }}>
        <div className="panel-head">
          <span>Fleet Sync</span>
          <span className="tag">{frame.fleet_sync.toFixed(1)}</span>
        </div>
        <div className="panel-body">
          <div className="sync-bar-wrap">
            <div
              className="sync-bar-fill"
              style={{ width: `${Math.max(0, Math.min(100, frame.fleet_sync))}%` }}
            />
          </div>
        </div>
      </div>
    </div>
  );
}
