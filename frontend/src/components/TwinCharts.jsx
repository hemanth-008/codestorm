/**
 * TwinCharts - 4 mini sparklines comparing twin vs real telemetry.
 */
import { ResponsiveContainer, LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip } from 'recharts';

function Spark({ data, dataKeys, colors, domain }) {
  return (
    <ResponsiveContainer width="100%" height={140}>
      <LineChart data={data} margin={{ top: 6, right: 8, bottom: 0, left: 0 }}>
        <CartesianGrid stroke="#CFCABB" strokeDasharray="3 3" />
        <XAxis dataKey="t" hide />
        <YAxis
          domain={domain}
          width={36}
          stroke="#161616"
          tick={{ fontSize: 11, fontFamily: "Consolas" }}
        />
        <Tooltip
          contentStyle={{
            background: "#F8F6EE",
            border: "1px solid #161616",
            borderRadius: 0,
            fontFamily: "Consolas",
            fontSize: 12,
          }}
          labelStyle={{ display: 'none' }}
        />
        {dataKeys.map((k, i) => (
          <Line
            key={k}
            type="monotone"
            dataKey={k}
            stroke={colors[i]}
            strokeWidth={1.5}
            strokeDasharray={k.startsWith('pred') ? '3 3' : '0'}
            dot={false}
            isAnimationActive={false}
          />
        ))}
      </LineChart>
    </ResponsiveContainer>
  );
}

export default function TwinCharts({ history }) {
  if (!history || history.length === 0) {
    return <div className="empty-state">No history yet...</div>;
  }
  
  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
      <div>
        <div className="kpi-label">Position Residual (m)</div>
        <Spark data={history} dataKeys={['residual_pos']} colors={['#FF5A1F']} domain={['auto', 'auto']} />
      </div>
      <div>
        <div className="kpi-label">Battery (%)</div>
        <Spark data={history} dataKeys={['est_battery', 'pred_battery']} colors={['#161616', '#6B675B']} domain={['auto', 'auto']} />
      </div>
      <div>
        <div className="kpi-label">Temp (°C)</div>
        <Spark data={history} dataKeys={['est_temp', 'pred_temp']} colors={['#FF5A1F', '#6B675B']} domain={['auto', 'auto']} />
      </div>
      <div>
        <div className="kpi-label">Vibration (g)</div>
        <Spark data={history} dataKeys={['est_vib', 'pred_vib']} colors={['#161616', '#6B675B']} domain={['auto', 'auto']} />
      </div>
    </div>
  );
}
