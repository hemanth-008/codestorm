import { useMemo } from 'react';

/**
 * Renders the 200x200 metric arena with a 10m grid,
 * all robots, their planned missions, and actual trails.
 */
export default function FleetMap({ frame, trails }) {
  // Generate a grid every 10m up to 200m
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

  return (
    <svg className="map-svg" viewBox="0 0 200 200" style={{ transform: 'scaleY(-1)' }}>
      {/* Background Grid */}
      {gridLines}
      
      {/* Draw each robot's mission plan and trail */}
      {frame?.robots.map((r) => {
        const tr = trails[r.robot_id] || [];
        
        const mission = r.mission;
        let routePath = '';
        
        if (mission && mission.waypoints.length > 0) {
          routePath = mission.waypoints.map(p => `${p.x},${p.y}`).join(' ');
          if (mission.loop) {
            routePath += ` ${mission.waypoints[0].x},${mission.waypoints[0].y}`;
          }
        }

        return (
          <g key={`map-robot-${r.robot_id}`}>
            {/* Mission Plan (dashed ghost) */}
            {routePath && (
              <polyline 
                points={routePath} 
                fill="none" 
                stroke="#161616" 
                strokeWidth="0.8" 
                strokeDasharray="2 2" 
                opacity={0.5}
              />
            )}
            
            {/* Waypoints */}
            {mission?.waypoints.map((wp, i) => (
              <g key={`wp-${r.robot_id}-${i}`}>
                <rect x={wp.x - 1.5} y={wp.y - 1.5} width="3" height="3" fill="#F1EEE4" stroke="#161616" strokeWidth="0.4" />
                <text x={wp.x + 2} y={wp.y - 2} fontSize="3" fontFamily="Consolas" fill="#161616" transform="scale(1, -1)">
                  {`W${i}`}
                </text>
              </g>
            ))}

            {/* Actual Trail (solid) */}
            {tr.length > 1 && (
              <polyline 
                points={tr.map(p => p.join(',')).join(' ')} 
                fill="none" 
                stroke="#FF5A1F" 
                strokeWidth="1.2" 
              />
            )}

            {/* Robot Marker */}
            {r.telemetry && (
              <g transform={`translate(${r.telemetry.x}, ${r.telemetry.y})`}>
                {/* Heading line */}
                <line 
                  x1="0" y1="0" 
                  x2={8 * Math.cos(r.telemetry.heading)} 
                  y2={8 * Math.sin(r.telemetry.heading)} 
                  stroke="#161616" 
                  strokeWidth="1" 
                />
                
                {/* Marker body based on type */}
                {r.robot_type === 'drone' ? (
                  <path d="M 0 -3 L 3 3 L -3 3 Z" fill="#FF5A1F" stroke="#161616" strokeWidth="0.5" transform={`rotate(${(r.telemetry.heading * 180 / Math.PI) - 90})`} />
                ) : r.robot_type === 'agv' ? (
                  <rect x="-3" y="-3" width="6" height="6" fill="#FF5A1F" stroke="#161616" strokeWidth="0.5" transform={`rotate(${r.telemetry.heading * 180 / Math.PI})`} />
                ) : (
                  <circle cx="0" cy="0" r="3" fill="#FF5A1F" stroke="#161616" strokeWidth="0.5" />
                )}
                
                {/* Label */}
                <text x="4" y="-4" fontSize="4" fontFamily="Consolas" fill="#161616" transform="scale(1, -1)">
                  {r.name}
                </text>
              </g>
            )}
          </g>
        );
      })}
    </svg>
  );
}
