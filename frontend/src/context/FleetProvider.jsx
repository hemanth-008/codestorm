/**
 * FleetProvider – context for sharing the fleet stream across all pages.
 *
 * Wraps the useFleetStream hook so every page can access the latest frame,
 * events, and connection status without duplicating the SSE connection.
 */

import { createContext, useContext } from 'react';
import { useFleetStream } from '../hooks/useFleetStream';

const FleetContext = createContext(null);

export function FleetProvider({ children }) {
  const stream = useFleetStream();
  return (
    <FleetContext.Provider value={stream}>
      {children}
    </FleetContext.Provider>
  );
}

/**
 * @returns {import('../hooks/useFleetStream').FleetStreamState}
 */
export function useFleet() {
  const ctx = useContext(FleetContext);
  if (!ctx) throw new Error('useFleet must be inside <FleetProvider>');
  return ctx;
}
