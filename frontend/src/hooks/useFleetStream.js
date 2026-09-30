/**
 * useFleetStream – SSE hook that provides the latest StreamFrame.
 *
 * When VITE_USE_MOCK=1 (default), uses the built-in mock stream generator.
 * Otherwise opens an SSE connection to the backend /api/stream endpoint.
 *
 * @module hooks/useFleetStream
 */

import { useState, useEffect, useRef, useCallback } from 'react';
import { openStream } from '../api';
import { startMockStream } from '../mock';

const USE_MOCK = import.meta.env.VITE_USE_MOCK !== '0';
const MAX_EVENTS = 200;

/**
 * @typedef {Object} FleetStreamState
 * @property {import('../types').StreamFrame|null} frame - latest frame
 * @property {import('../types').Event[]} events - accumulated events (newest first, capped at MAX_EVENTS)
 * @property {boolean} connected - whether the stream is active
 * @property {number} frameCount - total frames received
 */

/**
 * Subscribe to the fleet stream (mock or real SSE).
 * @returns {FleetStreamState}
 */
export function useFleetStream() {
  const [frame, setFrame] = useState(null);
  const [events, setEvents] = useState([]);
  const [connected, setConnected] = useState(false);
  const [frameCount, setFrameCount] = useState(0);
  const cleanupRef = useRef(null);

  const handleFrame = useCallback((/** @type {import('../types').StreamFrame} */ f) => {
    if (f.robots && f.robots.length > 0 && f.ts > 1000000000) { f.ts = f.robots[0].telemetry.ts; }; setFrame(f);
    setFrameCount(c => c + 1);
    setConnected(true);
    if (f.events && f.events.length > 0) {
      setEvents(prev => [...f.events, ...prev].slice(0, MAX_EVENTS));
    }
  }, []);

  useEffect(() => {
    if (USE_MOCK) {
      const stop = startMockStream(handleFrame);
      cleanupRef.current = stop;
      return stop;
    }

    // Real SSE
    const es = openStream();

    es.onmessage = (evt) => {
      try {
        const data = JSON.parse(evt.data);
        handleFrame(data);
      } catch {
        // malformed frame, skip
      }
    };

    es.onopen = () => setConnected(true);

    es.onerror = () => {
      setConnected(false);
      // EventSource auto-reconnects
    };

    cleanupRef.current = () => es.close();
    return () => es.close();
  }, [handleFrame]);

  return { frame, events, connected, frameCount };
}
