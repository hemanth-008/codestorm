/**
 * FleetOverview (Task C2)
 *
 * Shows the metric arena map, robot cards, alert feed, and fleet sync gauge.
 */
import { useState, useEffect } from 'react';
import { useFleet } from '../context/FleetProvider';
import FleetMap from '../components/FleetMap';
import RobotCard from '../components/RobotCard';
import AlertFeed from '../components/AlertFeed';

export default function FleetOverview() {
  const { frame, events } = useFleet();
  const [trails, setTrails] = useState({});

  // Accumulate trails
  useEffect(() => {
    if (!frame) return;
    setTrails((prev) => {
      const next = { ...prev };
      for (const r of frame.robots) {
        if (!r.telemetry) continue;
        const pts = next[r.robot_id] || [];
        // keep last 50 points
        next[r.robot_id] = [...pts, [r.telemetry.x, r.telemetry.y]].slice(-50);
      }
      return next;
    });
  }, [frame]);

  if (!frame) {
    return <div className="empty-state">Waiting for stream data…</div>;
  }

  return (
    <div>
      <div className="panels">
        {/* Left column: Map and Sync Gauge */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
          <div className="panel">
            <div className="panel-head">
              <span>Fleet Patrol Map</span>
              <span className="tag">200 x 200 m</span>
            </div>
            <div className="panel-body">
              <FleetMap frame={frame} trails={trails} />
            </div>
          </div>
          
          <div className="panel">
            <div className="panel-head">
              <span>Fleet Sync</span>
              <span className="tag">{frame.fleet_sync?.toFixed(1) ?? '--'}</span>
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

        {/* Right column: Cards and Alerts */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            {(() => {
              if (frame.robots.length > 0 && frame.robots.every(r => r.health?.status === 'critical')) {
                return (
                  <div className="error-state" style={{ margin: 0 }}>
                    <strong>FLEET DEGRADED</strong>
                    <br /><br />
                    All robots are in critical state.<br />
                    Please reset the scenario from the top bar.
                  </div>
                );
              }
              return frame.robots.map((r) => (
                <RobotCard key={r.robot_id} robot={r} />
              ));
            })()}
          </div>

          <AlertFeed events={events} />
        </div>
      </div>
    </div>
  );
}
