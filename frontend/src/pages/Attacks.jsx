/**
 * Attacks (Task C4)
 *
 * Adversarial panel for injecting faults and monitoring detections.
 */
import { useState } from 'react';
import { useFleet } from '../context/FleetProvider';
import { injectAttack, clearAttacks, getToken } from '../api';

const ROBOT_IDS = ['R1', 'D1', 'G1'];
const ATTACK_KINDS = ['noise', 'dropout', 'spoof_freeze', 'spoof_jump', 'spoof_drift', 'spoof_battery'];

export default function Attacks() {
  const { frame, events } = useFleet();
  
  const [robotId, setRobotId] = useState('R1');
  const [kind, setKind] = useState('noise');
  const [magnitude, setMagnitude] = useState(1.0);
  const [duration, setDuration] = useState(10.0);
  const [loading, setLoading] = useState(false);

  let isOperator = true;
  const token = getToken();
  if (token) {
    try {
      const payload = JSON.parse(atob(token.split('.')[1]));
      isOperator = payload.role === 'operator';
    } catch { }
  }

  const handleInject = async () => {
    setLoading(true);
    try {
      await injectAttack({
        robot_id: robotId,
        kind,
        magnitude: parseFloat(magnitude),
        duration_s: parseFloat(duration)
      });
    } catch (e) {
      console.error(e);
    }
    setLoading(false);
  };

  const handleClearAll = async () => {
    setLoading(true);
    try {
      await clearAttacks({}); // Clear all
    } catch (e) {
      console.error(e);
    }
    setLoading(false);
  };

  // Derive detection status from recent events (last 15 seconds)
  const recentEvents = events.filter(e => (frame?.ts || 0) - e.ts < 15);
  
  const getDetections = (rid) => {
    const evts = recentEvents.filter(e => e.robot_id === rid);
    const flags = new Set();
    if (evts.some(e => e.kind === 'spoof_suspected')) flags.add('SPOOF');
    if (evts.some(e => e.kind === 'noise_high' && !evts.some(c => c.kind === 'noise_cleared' && c.ts > e.ts))) flags.add('NOISE');
    if (evts.some(e => e.kind === 'dropout' && !evts.some(c => c.kind === 'link_recovered' && c.ts > e.ts))) flags.add('DROPOUT');
    if (evts.some(e => e.kind === 'deviation' && !evts.some(c => c.kind === 'deviation_cleared' && c.ts > e.ts))) flags.add('DEVIATION');
    return Array.from(flags);
  };

  return (
    <div className="panels">
      <div className="panel">
        <div className="panel-head">
          <span>Adversarial Injector</span>
          <span className="tag">Red Team</span>
        </div>
        <div className="panel-body" style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          
          <div>
            <div className="kpi-label">Target Robot</div>
            <div className="btn-row" style={{ marginTop: 6 }}>
              {ROBOT_IDS.map(rid => (
                <button 
                  key={rid}
                  className={`btn ${robotId === rid ? 'btn-active' : ''}`}
                  onClick={() => setRobotId(rid)}
                >
                  {rid}
                </button>
              ))}
            </div>
          </div>

          <div>
            <div className="kpi-label">Attack Type</div>
            <select 
              className="counter" 
              style={{ width: '100%', marginTop: 6, fontSize: 14, fontFamily: 'var(--mono)', borderRadius: 0, padding: 8 }}
              value={kind}
              onChange={(e) => setKind(e.target.value)}
            >
              {ATTACK_KINDS.map(k => <option key={k} value={k}>{k}</option>)}
            </select>
          </div>

          <div style={{ display: 'flex', gap: 12 }}>
            <div style={{ flex: 1 }}>
              <div className="kpi-label">Magnitude</div>
              <input 
                type="number" 
                className="counter"
                style={{ width: '100%', marginTop: 6, fontSize: 14, fontFamily: 'var(--mono)', borderRadius: 0, padding: 8 }}
                step="0.1"
                value={magnitude}
                onChange={(e) => setMagnitude(e.target.value)}
                disabled={kind === 'dropout' || kind === 'spoof_freeze'}
              />
            </div>
            <div style={{ flex: 1 }}>
              <div className="kpi-label">Duration (s)</div>
              <input 
                type="number" 
                className="counter"
                style={{ width: '100%', marginTop: 6, fontSize: 14, fontFamily: 'var(--mono)', borderRadius: 0, padding: 8 }}
                step="1"
                value={duration}
                onChange={(e) => setDuration(e.target.value)}
              />
            </div>
          </div>

          <div className="btn-row" style={{ marginTop: 8 }}>
            <button className="btn" style={{ flex: 1, padding: 12, fontWeight: 'bold' }} onClick={handleInject} disabled={loading || !isOperator}>
              INJECT FAULT
            </button>
            <button className="btn" style={{ padding: 12 }} onClick={handleClearAll} disabled={loading || !isOperator}>
              CLEAR ALL
            </button>
          </div>
          {!isOperator && <div className="mono-sm" style={{ marginTop: 6, color: 'var(--muted)', textAlign: 'center' }}>Viewer access only</div>}
        </div>
      </div>

      <div className="panel">
        <div className="panel-head">
          <span>Live Detection Status</span>
          <span className="tag">Blue Team</span>
        </div>
        <div className="panel-body">
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            {ROBOT_IDS.map(rid => {
              const r = frame?.robots.find(x => x.robot_id === rid);
              const det = getDetections(rid);
              const activeAttacks = r?.active_attacks || [];
              
              return (
                <div key={rid} style={{ paddingBottom: 16, borderBottom: '1px dashed var(--grid)' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
                    <span className="mono-sm" style={{ fontWeight: 'bold', fontSize: 14 }}>{rid} {r?.name}</span>
                    <span className="mono-sm">
                      Sync: {r ? r.twin.sync_score.toFixed(0) : '--'}
                    </span>
                  </div>
                  
                  <div className="kpi-label">Active Detections</div>
                  <div style={{ display: 'flex', gap: 8, marginTop: 6, flexWrap: 'wrap', minHeight: 28 }}>
                    {det.length === 0 && <span className="mono-sm" style={{ color: 'var(--muted)', marginTop: 4 }}>None</span>}
                    {det.map(d => (
                      <span key={d} className="detection-chip active">
                        {d}
                      </span>
                    ))}
                  </div>

                  {activeAttacks.length > 0 && (
                    <div style={{ marginTop: 12 }}>
                      <div className="kpi-label">Ground Truth Attacks</div>
                      <div className="mono-sm" style={{ color: 'var(--signal)', marginTop: 4 }}>
                        {activeAttacks.join(', ')}
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}
