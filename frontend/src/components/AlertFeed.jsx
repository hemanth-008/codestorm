/**
 * AlertFeed - displays a scrolling list of recent events.
 */
export default function AlertFeed({ events }) {
  return (
    <div className="panel">
      <div className="panel-head">
        <span>Live Alert Feed</span>
        <span className="tag">{events.length}</span>
      </div>
      <div className="log" style={{ maxHeight: 400 }}>
        {events.length === 0 && <div className="log-empty">Waiting for events...</div>}
        {events.map((e) => (
          <div key={e.id} className={`log-row alert-pulse ${e.severity !== 'info' ? 'warn' : ''}`}>
            <span className="t">{e.ts.toFixed(1)}s</span>
            <span className="m">[{e.robot_id || 'SYS'}] {e.message}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
