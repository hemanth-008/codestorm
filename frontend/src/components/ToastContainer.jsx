/**
 * ToastContainer – renders auto-dismissing toast notifications.
 *
 * Toasts appear in the bottom-right corner when critical events arrive
 * on the fleet stream. Each toast auto-dismisses after 5 seconds.
 */
import { useNotifications } from '../context/NotificationProvider';

export default function ToastContainer() {
  const { toasts, dismissToast } = useNotifications();

  if (toasts.length === 0) return null;

  return (
    <div
      style={{
        position: 'fixed',
        bottom: 20,
        right: 20,
        zIndex: 2000,
        display: 'flex',
        flexDirection: 'column-reverse',
        gap: 8,
        maxWidth: 360,
      }}
    >
      {toasts.slice(0, 5).map((toast) => (
        <div
          key={toast.id}
          className="toast-enter"
          style={{
            background: 'var(--panel)',
            border: '1.5px solid var(--ink)',
            borderLeft: '4px solid var(--signal)',
            padding: '10px 12px',
            fontFamily: 'var(--mono)',
            fontSize: 12,
            display: 'flex',
            gap: 10,
            alignItems: 'flex-start',
            boxShadow: '4px 4px 0 rgba(0,0,0,0.1)',
            animation: 'toastSlideIn 0.3s ease-out',
          }}
        >
          <span style={{ color: 'var(--signal)', fontWeight: 700, fontSize: 14, lineHeight: 1 }}>⚠</span>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.04em', fontSize: 11 }}>
              {toast.event.kind.replace(/_/g, ' ')}
              {toast.event.robot_id && <span style={{ color: 'var(--muted)', fontWeight: 400, marginLeft: 6 }}>{toast.event.robot_id}</span>}
            </div>
            <div style={{ color: 'var(--muted)', marginTop: 3, fontSize: 11, lineHeight: 1.3 }}>
              {toast.event.message}
            </div>
          </div>
          <button
            onClick={() => dismissToast(toast.id)}
            style={{
              background: 'transparent',
              border: 'none',
              cursor: 'pointer',
              fontFamily: 'var(--mono)',
              fontSize: 14,
              color: 'var(--muted)',
              padding: 0,
              lineHeight: 1,
            }}
            aria-label="Dismiss"
          >
            ×
          </button>
        </div>
      ))}
    </div>
  );
}
