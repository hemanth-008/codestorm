/**
 * NotificationProvider – global notification context.
 *
 * Watches the fleet stream for critical-severity events and emits toasts.
 * Maintains an unread count and a notification history accessible from
 * a bell icon dropdown in the Shell header.
 *
 * Critical event kinds that trigger toasts:
 *  - spoof_suspected, dropout, maintenance_due, health_warning (critical)
 */
import { createContext, useContext, useState, useCallback, useEffect, useRef } from 'react';
import { useFleet } from './FleetProvider';

const NotifContext = createContext(null);

const CRITICAL_KINDS = new Set([
  'spoof_suspected',
  'dropout',
  'maintenance_due',
  'health_warning',
]);

const MAX_HISTORY = 80;
const TOAST_DURATION_MS = 5000;

let _notifIdCounter = 0;

export function NotificationProvider({ children }) {
  const { events } = useFleet();
  const [history, setHistory] = useState([]);
  const [unread, setUnread] = useState(0);
  const [toasts, setToasts] = useState([]);
  const seenRef = useRef(new Set());

  // Watch for new critical events
  useEffect(() => {
    if (!events || events.length === 0) return;

    const newCritical = [];
    for (const evt of events) {
      if (seenRef.current.has(evt.id)) break; // already seen (events are newest-first)
      if (CRITICAL_KINDS.has(evt.kind) || evt.severity === 'critical') {
        newCritical.push(evt);
      }
      seenRef.current.add(evt.id);
    }

    if (newCritical.length > 0) {
      setHistory((prev) => [...newCritical, ...prev].slice(0, MAX_HISTORY));
      setUnread((prev) => prev + newCritical.length);

      // Create toasts
      const newToasts = newCritical.map((evt) => ({
        id: `toast-${++_notifIdCounter}`,
        event: evt,
        createdAt: Date.now(),
      }));
      setToasts((prev) => [...newToasts, ...prev]);

      // Auto-dismiss after TOAST_DURATION_MS
      for (const t of newToasts) {
        setTimeout(() => {
          setToasts((prev) => prev.filter((x) => x.id !== t.id));
        }, TOAST_DURATION_MS);
      }
    }
  }, [events]);

  const markRead = useCallback(() => setUnread(0), []);

  const dismissToast = useCallback((id) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const clearHistory = useCallback(() => {
    setHistory([]);
    setUnread(0);
  }, []);

  return (
    <NotifContext.Provider value={{ history, unread, toasts, markRead, dismissToast, clearHistory }}>
      {children}
    </NotifContext.Provider>
  );
}

export function useNotifications() {
  const ctx = useContext(NotifContext);
  if (!ctx) throw new Error('useNotifications must be inside <NotificationProvider>');
  return ctx;
}
