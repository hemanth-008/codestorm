/**
 * DecisionPanel - shows current decision and manual override buttons.
 */
import { useState } from 'react';

export default function DecisionPanel({ decision, onOverride }) {
  const [loading, setLoading] = useState(false);
  const warn = decision && decision.action !== 'CONTINUE';

  const handle = async (action, reason) => {
    setLoading(true);
    await onOverride(action, reason);
    setLoading(false);
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <div>
        <div className="kpi-label">Current Action</div>
        <div className={warn ? 'action-badge warn' : 'action-badge'}>
          {decision ? decision.action.replace(/_/g, ' ') : '--'}
        </div>
        {decision?.override_active && (
          <span className="mono-sm" style={{ color: 'var(--signal)', marginLeft: 8 }}>
            (OVERRIDE ACTIVE)
          </span>
        )}
      </div>

      <div>
        <div className="kpi-label">Reasoning</div>
        <div className="decision-reason">
          {decision ? decision.reason : 'Waiting for data...'}
        </div>
      </div>
      
      <div>
        <div className="kpi-label">Confidence</div>
        <div className="mono-sm">
          {decision ? `${(decision.confidence * 100).toFixed(0)}%` : '--'}
        </div>
      </div>

      <div>
        <div className="kpi-label">Manual Override (15s)</div>
        <div className="btn-row">
          <button className="btn" disabled={loading} onClick={() => handle('CONTINUE', 'Operator resumed normal patrol')}>
            Continue
          </button>
          <button className="btn" disabled={loading} onClick={() => handle('REROUTE', 'Operator requested reroute')}>
            Reroute
          </button>
          <button className="btn" disabled={loading} onClick={() => handle('RETURN_TO_BASE', 'Operator recalled unit to base')}>
            Return to base
          </button>
        </div>
      </div>
    </div>
  );
}
