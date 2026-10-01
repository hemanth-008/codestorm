/**
 * NotificationBell – bell icon with unread badge and dropdown history.
 *
 * Sits in the Shell header. Clicking toggles a dropdown of recent
 * critical notifications. Unread count resets on open.
 */
import { useState, useRef, useEffect } from 'react';
import { useNotifications } from '../context/NotificationProvider';

/** Format sim-seconds timestamp */
function fmtTs(ts) {
  if (ts == null) return '';
  const m = Math.floor(ts / 60);
  const s = Math.floor(ts % 60);
  return `${m}:${s.toString().padStart(2, '0')}`;
}

export default function NotificationBell() {
  const { history, unread, markRead, clearHistory } = useNotifications();
  const [open, setOpen] = useState(false);
  const ref = useRef(null);

  // Close dropdown when clicking outside
  useEffect(() => {
    if (!open) return;
    const handler = (e) => {
      if (ref.current && !ref.current.contains(e.target)) {
        setOpen(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [open]);

  const toggle = () => {
    setOpen((v) => !v);
    if (!open) markRead();
  };

  return (
    <div ref={ref} style={{ position: 'relative', display: 'inline-flex', alignItems: 'center' }}>
      <button
        onClick={toggle}
        aria-label="Notifications"
        style={{
          background: 'transparent',
          border: '1.5px solid var(--ink)',
          cursor: 'pointer',
          padding: '4px 8px',
          fontFamily: 'var(--mono)',
          fontSize: 16,
          lineHeight: 1,
          position: 'relative',
          color: 'var(--ink)',
        }}
      >
        🔔
        {unread > 0 && (
          <span
            style={{
              position: 'absolute',
              top: -6,
              right: -6,
              background: 'var(--signal)',
              color: 'var(--paper)',
              fontFamily: 'var(--mono)',
              fontSize: 10,
              fontWeight: 700,
              minWidth: 16,
              height: 16,
              borderRadius: 8,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              padding: '0 3px',
            }}
          >
            {unread > 99 ? '99+' : unread}
          </span>
        )}
      </button>

      {open && (
        <div
          className="notif-dropdown"
          style={{
            position: 'absolute',
            top: '100%',
            right: 0,
            marginTop: 6,
            width: 340,
            maxHeight: 360,
            overflowY: 'auto',
            background: 'var(--panel)',
            border: '1.5px solid var(--ink)',
            zIndex: 1000,
            boxShadow: '4px 4px 0 rgba(0,0,0,0.08)',
          }}
        >
          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              padding: '8px 10px',
              borderBottom: '1px solid var(--ink)',
              fontFamily: 'var(--mono)',
              fontSize: 11,
              textTransform: 'uppercase',
              letterSpacing: '0.06em',
            }}
          >
            <span>Notifications</span>
            {history.length > 0 && (
              <button
                onClick={clearHistory}
                style={{
                  background: 'transparent',
                  border: 'none',
                  cursor: 'pointer',
                  fontFamily: 'var(--mono)',
                  fontSize: 10,
                  color: 'var(--signal)',
                  textTransform: 'uppercase',
                }}
              >
                Clear
              </button>
            )}
          </div>

          {history.length === 0 ? (
            <div style={{ padding: '20px 10px', textAlign: 'center', fontFamily: 'var(--mono)', fontSize: 12, color: 'var(--muted)' }}>
              No critical alerts yet.
            </div>
          ) : (
            history.map((evt) => (
              <div
                key={evt.id}
                style={{
                  padding: '8px 10px',
                  borderBottom: '1px dashed var(--grid)',
                  display: 'flex',
                  gap: 8,
                  alignItems: 'flex-start',
                }}
              >
                <span
                  style={{
                    width: 8,
                    height: 8,
                    minWidth: 8,
                    background: evt.severity === 'critical' ? 'var(--signal)' : 'var(--ink)',
                    marginTop: 4,
                  }}
                />
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontFamily: 'var(--mono)', fontSize: 12, fontWeight: 700 }}>
                    {evt.kind.replace(/_/g, ' ')}
                    {evt.robot_id && <span style={{ color: 'var(--muted)', fontWeight: 400, marginLeft: 6 }}>{evt.robot_id}</span>}
                  </div>
                  <div style={{ fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--muted)', marginTop: 2 }}>
                    {evt.message}
                  </div>
                </div>
                <span style={{ fontFamily: 'var(--mono)', fontSize: 10, color: 'var(--muted)', whiteSpace: 'nowrap' }}>
                  T={fmtTs(evt.ts)}
                </span>
              </div>
            ))
          )}
        </div>
      )}
    </div>
  );
}
