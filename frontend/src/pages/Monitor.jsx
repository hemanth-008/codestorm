/**
 * Monitor (Task C7)
 *
 * System monitor page showing health JSON and ingest stats.
 */
import { useState, useEffect } from 'react';
import { useFleet } from '../context/FleetProvider';
import { getHealth } from '../api';

export default function Monitor() {
  const { frame, connected } = useFleet();
  const [healthData, setHealthData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchHealth = async () => {
      try {
        const res = await getHealth();
        setHealthData(res);
      } catch (e) {
        setHealthData({ status: 'unreachable', error: e.message });
      }
      setLoading(false);
    };
    fetchHealth();
    const id = setInterval(fetchHealth, 10000);
    return () => clearInterval(id);
  }, []);

  return (
    <div className="panels">
      <div className="panel">
        <div className="panel-head">
          <span>Ingest Statistics</span>
          <span className="tag">Stream</span>
        </div>
        <div className="panel-body">
          {!frame ? (
            <div className="mono-sm" style={{ color: 'var(--muted)' }}>No stream data available.</div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
              <div>
                <div className="kpi-label">Messages per second</div>
                <div className="kpi-value" style={{ fontSize: 32 }}>
                  {frame.ingest.msgs_per_s.toFixed(1)}
                </div>
              </div>
              <div>
                <div className="kpi-label">Dropped Packets</div>
                <div className="kpi-value" style={{ fontSize: 32, color: frame.ingest.dropped > 0 ? 'var(--signal)' : 'inherit' }}>
                  {frame.ingest.dropped}
                </div>
              </div>
              <div>
                <div className="kpi-label">Lag (ms)</div>
                <div className="kpi-value" style={{ fontSize: 32 }}>
                  {frame.ingest.lag_ms.toFixed(1)}
                </div>
              </div>
              <div>
                <div className="kpi-label">Connection Status</div>
                <div className={`action-badge ${connected ? '' : 'warn'}`} style={{ marginTop: 6 }}>
                  {connected ? 'CONNECTED' : 'DISCONNECTED'}
                </div>
              </div>
            </div>
          )}
        </div>
      </div>

      <div className="panel">
        <div className="panel-head">
          <span>Backend Health Check</span>
          <span className="tag">/health</span>
        </div>
        <div className="panel-body" style={{ overflowX: 'auto' }}>
          {loading ? (
            <div className="mono-sm" style={{ color: 'var(--muted)' }}>Fetching health...</div>
          ) : (
            <pre style={{ margin: 0, fontFamily: 'var(--mono)', fontSize: 13, color: 'var(--ink)' }}>
              {JSON.stringify(healthData, null, 2)}
            </pre>
          )}
        </div>
      </div>
    </div>
  );
}
