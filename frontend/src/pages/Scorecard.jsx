/**
 * Scorecard (Task C5)
 *
 * Runs and displays the eval suite results.
 */
import { useState, useEffect } from 'react';
import { ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid } from 'recharts';
import { runEval, getEvalLatest } from '../api';

export default function Scorecard() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const fetchLatest = async () => {
    try {
      const res = await getEvalLatest();
      setData(res);
      setError(null);
    } catch (e) {
      if (e.message.includes('404')) {
        setData(null); // no eval yet
      } else {
        setError('Failed to fetch scorecard data');
      }
    }
  };

  useEffect(() => {
    fetchLatest();
  }, []);

  const handleRun = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await runEval(42);
      setData(res);
    } catch (e) {
      setError(e.message);
    }
    setLoading(false);
  };

  return (
    <div className="panels">
      <div className="panel" style={{ gridColumn: '1 / -1' }}>
        <div className="panel-head">
          <span>Attack Suite Scorecard</span>
          <span className="tag">EVAL-01</span>
        </div>
        <div className="panel-body">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span className="mono-sm">
              Runs headless scenarios to measure detection, false alarms, and RUL error.
            </span>
            <button className="btn" onClick={handleRun} disabled={loading} style={{ padding: '8px 24px', fontWeight: 'bold' }}>
              {loading ? 'RUNNING SUITE...' : 'RUN ATTACK SUITE'}
            </button>
          </div>
          {error && <div className="mono-sm" style={{ color: 'var(--signal)', marginTop: 12 }}>Error: {error}</div>}
        </div>
      </div>

      {!data && !loading && !error && (
        <div className="empty-state" style={{ gridColumn: '1 / -1' }}>
          No eval results found. Click "Run Attack Suite" to start.
        </div>
      )}

      {loading && !data && (
        <div className="empty-state" style={{ gridColumn: '1 / -1' }}>
          Running scenarios... this will take about 15 seconds.
        </div>
      )}

      {data && (
        <>
          {/* Summary KPIs */}
          <div className="panel" style={{ gridColumn: '1 / -1' }}>
            <div className="panel-head">
              <span>Overall Summary</span>
              <span className="tag">Seed {data.seed}</span>
            </div>
            <div className="panel-body">
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: 16 }}>
                <div>
                  <div className="kpi-label">Detection Rate</div>
                  <div className="kpi-value" style={{ fontSize: 28, color: data.summary.detection_rate < 0.8 ? 'var(--signal)' : 'inherit' }}>
                    {(data.summary.detection_rate * 100).toFixed(0)}<span className="kpi-unit">%</span>
                  </div>
                </div>
                <div>
                  <div className="kpi-label">False Alarms/Hr</div>
                  <div className="kpi-value" style={{ fontSize: 28, color: data.summary.false_alarms_per_hour > 10 ? 'var(--signal)' : 'inherit' }}>
                    {data.summary.false_alarms_per_hour.toFixed(1)}
                  </div>
                </div>
                <div>
                  <div className="kpi-label">Mean TTD</div>
                  <div className="kpi-value" style={{ fontSize: 28 }}>
                    {data.summary.mean_time_to_detect_s?.toFixed(1) || '--'}<span className="kpi-unit">s</span>
                  </div>
                </div>
                <div>
                  <div className="kpi-label">Mean Recovery</div>
                  <div className="kpi-value" style={{ fontSize: 28 }}>
                    {data.summary.mean_recovery_s?.toFixed(1) || '--'}<span className="kpi-unit">s</span>
                  </div>
                </div>
                <div>
                  <div className="kpi-label">RUL Error</div>
                  <div className="kpi-value" style={{ fontSize: 28 }}>
                    {data.summary.rul_error_pct != null ? (data.summary.rul_error_pct).toFixed(1) : '--'}<span className="kpi-unit">%</span>
                  </div>
                </div>
                <div>
                  <div className="kpi-label">Sync Clean</div>
                  <div className="kpi-value" style={{ fontSize: 28 }}>
                    {data.summary.mean_sync_clean.toFixed(0)}
                  </div>
                </div>
                <div>
                  <div className="kpi-label">Sync Attacked</div>
                  <div className="kpi-value" style={{ fontSize: 28, color: 'var(--signal)' }}>
                    {data.summary.mean_sync_attacked.toFixed(0)}
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Bar chart of Time to Detect */}
          <div className="panel">
            <div className="panel-head">
              <span>Time to Detect (s)</span>
              <span className="tag">Per Scenario</span>
            </div>
            <div className="panel-body" style={{ height: 300, paddingTop: 20 }}>
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={data.rows.filter(r => r.detected)} margin={{ top: 0, right: 0, bottom: 20, left: -20 }}>
                  <CartesianGrid stroke="#CFCABB" strokeDasharray="3 3" vertical={false} />
                  <XAxis 
                    dataKey="scenario" 
                    tick={{ fontSize: 10, fontFamily: "Consolas" }}
                    interval={0}
                    angle={-45}
                    textAnchor="end"
                  />
                  <YAxis tick={{ fontSize: 11, fontFamily: "Consolas" }} />
                  <Tooltip 
                    cursor={{ fill: 'rgba(0,0,0,0.05)' }}
                    contentStyle={{
                      background: "#F8F6EE", border: "1px solid #161616", borderRadius: 0, fontFamily: "Consolas", fontSize: 12,
                    }}
                  />
                  <Bar dataKey="time_to_detect_s" fill="#FF5A1F" name="TTD (s)" />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Table */}
          <div className="panel">
            <div className="panel-head">
              <span>Scenario Breakdown</span>
              <span className="tag">{data.rows.length} Scenarios</span>
            </div>
            <div className="panel-body" style={{ overflowX: 'auto', padding: 0 }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontFamily: 'var(--mono)', fontSize: 12, textAlign: 'left' }}>
                <thead style={{ borderBottom: '1.5px solid var(--ink)', background: 'var(--paper)' }}>
                  <tr>
                    <th style={{ padding: '8px 12px' }}>Scenario</th>
                    <th style={{ padding: '8px 12px' }}>Kind</th>
                    <th style={{ padding: '8px 12px' }}>Mag</th>
                    <th style={{ padding: '8px 12px' }}>Detected</th>
                    <th style={{ padding: '8px 12px' }}>TTD</th>
                    <th style={{ padding: '8px 12px' }}>FA</th>
                    <th style={{ padding: '8px 12px' }}>Min Sync</th>
                    <th style={{ padding: '8px 12px' }}>Recov</th>
                  </tr>
                </thead>
                <tbody>
                  {data.rows.map((r, i) => (
                    <tr key={i} style={{ borderBottom: '1px dashed var(--grid)' }}>
                      <td style={{ padding: '8px 12px' }}>{r.scenario}</td>
                      <td style={{ padding: '8px 12px' }}>{r.kind}</td>
                      <td style={{ padding: '8px 12px' }}>{r.magnitude}</td>
                      <td style={{ padding: '8px 12px' }}>
                        {r.kind !== 'clean' && (
                          <span className={r.detected ? '' : 'warn'} style={{ color: r.detected ? 'inherit' : 'var(--signal)', fontWeight: 'bold' }}>
                            {r.detected ? 'YES' : 'NO'}
                          </span>
                        )}
                      </td>
                      <td style={{ padding: '8px 12px' }}>{r.time_to_detect_s?.toFixed(1) || '--'}</td>
                      <td style={{ padding: '8px 12px', color: r.false_alarms > 0 ? 'var(--signal)' : 'inherit' }}>{r.false_alarms}</td>
                      <td style={{ padding: '8px 12px' }}>{r.min_sync.toFixed(0)}</td>
                      <td style={{ padding: '8px 12px' }}>{r.recovery_s?.toFixed(1) || '--'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
