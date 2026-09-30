/**
 * Sandbox (Task C6)
 *
 * Click-to-add waypoints on a map, simulate mission, and deploy.
 */
import { useState, useMemo } from 'react';
import { useFleet } from '../context/FleetProvider';
import { simulateMission, deployMission } from '../api';

const ROBOT_IDS = ['R1', 'D1', 'G1'];

export default function Sandbox() {
  const { frame } = useFleet();
  const [robotId, setRobotId] = useState('R1');
  const [waypoints, setWaypoints] = useState([]);
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const handleMapClick = (e) => {
    // Basic SVG click coordinate mapping
    const svg = e.currentTarget;
    const pt = svg.createSVGPoint();
    pt.x = e.clientX;
    pt.y = e.clientY;
    const svgP = pt.matrixTransform(svg.getScreenCTM().inverse());
    
    // Y is flipped in our viewBox vs display, but we applied scaleY(-1) so it maps directly!
    // Actually scaleY(-1) means screen Y increases downwards, SVG Y increases upwards.
    // getScreenCTM takes care of transformations.
    const newWp = { 
      x: Math.max(0, Math.min(200, svgP.x)), 
      y: Math.max(0, Math.min(200, svgP.y)),
      z: robotId === 'D1' ? 20 : 0
    };
    setWaypoints([...waypoints, newWp]);
    setResult(null); // invalidate previous sim
  };

  const handleSimulate = async () => {
    if (waypoints.length === 0) return;
    setLoading(true);
    setError(null);
    try {
      const res = await simulateMission({
        mission_id: `sandbox-${Date.now()}`,
        robot_id: robotId,
        waypoints,
        cruise_speed: robotId === 'D1' ? 6.0 : robotId === 'G1' ? 2.0 : 1.5,
        loop: false,
      });
      setResult(res);
    } catch (e) {
      // Mock stream will throw 501 Not Implemented because sandbox is backend only initially
      // But we show the error gracefully
      setError(e.message);
    }
    setLoading(false);
  };

  const handleDeploy = async () => {
    if (!result || !result.safe_to_deploy) return;
    setLoading(true);
    try {
      await deployMission({
        mission_id: result.mission_id,
        robot_id: robotId,
        waypoints,
        cruise_speed: robotId === 'D1' ? 6.0 : robotId === 'G1' ? 2.0 : 1.5,
        loop: false,
      });
      alert('Mission deployed successfully!');
      setWaypoints([]);
      setResult(null);
    } catch (e) {
      setError(e.message);
    }
    setLoading(false);
  };

  const gridLines = useMemo(() => {
    const lines = [];
    for (let i = 0; i <= 20; i++) {
      lines.push(
        <g key={`grid-${i}`}>
          <line x1={i * 10} y1="0" x2={i * 10} y2="200" stroke="#CFCABB" strokeWidth="0.5" />
          <line x1="0" y1={i * 10} x2="200" y2={i * 10} stroke="#CFCABB" strokeWidth="0.5" />
        </g>
      );
    }
    return lines;
  }, []);

  const robot = frame?.robots.find(r => r.robot_id === robotId);
  const startPos = robot ? { x: robot.telemetry.x, y: robot.telemetry.y } : null;

  return (
    <div className="panels">
      <div className="panel" style={{ gridColumn: '1 / -1' }}>
        <div className="panel-head">
          <span>Mission Sandbox</span>
          <span className="tag">What-If Engine</span>
        </div>
        <div className="panel-body" style={{ display: 'flex', gap: 24, flexWrap: 'wrap' }}>
          
          <div style={{ flex: 1, minWidth: 300 }}>
            <div className="kpi-label">Select Robot</div>
            <div className="btn-row" style={{ marginTop: 6, marginBottom: 16 }}>
              {ROBOT_IDS.map(rid => (
                <button 
                  key={rid}
                  className={`btn ${robotId === rid ? 'btn-active' : ''}`}
                  onClick={() => { setRobotId(rid); setWaypoints([]); setResult(null); }}
                >
                  {rid}
                </button>
              ))}
            </div>

            <div className="kpi-label">Waypoints ({waypoints.length})</div>
            <div className="mono-sm" style={{ marginTop: 6, marginBottom: 16, minHeight: 40 }}>
              {waypoints.length === 0 ? 'Click on the map to add waypoints.' : 
                waypoints.map(w => `[${w.x.toFixed(0)}, ${w.y.toFixed(0)}]`).join(' → ')
              }
            </div>

            <div className="btn-row">
              <button className="btn" style={{ fontWeight: 'bold' }} onClick={handleSimulate} disabled={loading || waypoints.length === 0}>
                SIMULATE
              </button>
              <button className="btn" onClick={() => { setWaypoints([]); setResult(null); }} disabled={loading || waypoints.length === 0}>
                CLEAR
              </button>
            </div>

            {error && <div className="mono-sm" style={{ color: 'var(--signal)', marginTop: 12 }}>{error}</div>}

            {result && (
              <div style={{ marginTop: 24, padding: 12, border: '1.5px solid var(--ink)', background: 'var(--paper)' }}>
                <div className="kpi-label" style={{ marginBottom: 8 }}>Simulation Result</div>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                  <div>
                    <span className="mono-sm">ETA:</span><br/>
                    <strong>{result.eta_s.toFixed(1)} s</strong>
                  </div>
                  <div>
                    <span className="mono-sm">End Battery:</span><br/>
                    <strong style={{ color: result.end_battery < 15 ? 'var(--signal)' : 'inherit' }}>
                      {result.end_battery.toFixed(1)}%
                    </strong>
                  </div>
                  <div>
                    <span className="mono-sm">Risk Score:</span><br/>
                    <strong style={{ color: result.risk > 0.5 ? 'var(--signal)' : 'inherit' }}>
                      {(result.risk * 100).toFixed(0)}%
                    </strong>
                  </div>
                  <div>
                    <span className="mono-sm">Safety Gate:</span><br/>
                    <strong style={{ color: result.safe_to_deploy ? 'inherit' : 'var(--signal)' }}>
                      {result.safe_to_deploy ? 'PASS' : 'FAIL'}
                    </strong>
                  </div>
                </div>
                
                {result.violations.length > 0 && (
                  <div className="mono-sm warn" style={{ marginTop: 12 }}>
                    <strong>Violations:</strong><br/>
                    {result.violations.join(', ')}
                  </div>
                )}

                <button 
                  className="btn" 
                  style={{ width: '100%', marginTop: 16, fontWeight: 'bold' }} 
                  onClick={handleDeploy} 
                  disabled={loading || !result.safe_to_deploy}
                >
                  DEPLOY TO FLEET
                </button>
              </div>
            )}
          </div>

          <div style={{ flex: 2, minWidth: 400, border: '1.5px solid var(--ink)', cursor: 'crosshair' }}>
            <svg viewBox="0 0 200 200" style={{ width: '100%', height: 'auto', display: 'block', transform: 'scaleY(-1)' }} onClick={handleMapClick}>
              {gridLines}

              {/* Start Pos */}
              {startPos && (
                <circle cx={startPos.x} cy={startPos.y} r="3" fill="#161616" />
              )}
              
              {/* Draft path lines */}
              {waypoints.length > 0 && startPos && (
                <polyline 
                  points={`${startPos.x},${startPos.y} ` + waypoints.map(p => `${p.x},${p.y}`).join(' ')} 
                  fill="none" stroke="#161616" strokeWidth="0.8" strokeDasharray="3 3" opacity={0.5} 
                />
              )}

              {/* Simulated path */}
              {result?.path && result.path.length > 0 && (
                <polyline 
                  points={result.path.map(p => p.join(',')).join(' ')} 
                  fill="none" stroke="#FF5A1F" strokeWidth="1.2" 
                />
              )}

              {/* Waypoints */}
              {waypoints.map((wp, i) => (
                <g key={i}>
                  <rect x={wp.x - 2} y={wp.y - 2} width="4" height="4" fill="#F1EEE4" stroke="#161616" strokeWidth="0.5" />
                  <text x={wp.x + 3} y={wp.y - 3} fontSize="4" fontFamily="Consolas" fill="#161616" transform="scale(1, -1)">
                    {i+1}
                  </text>
                </g>
              ))}
            </svg>
          </div>

        </div>
      </div>
    </div>
  );
}
