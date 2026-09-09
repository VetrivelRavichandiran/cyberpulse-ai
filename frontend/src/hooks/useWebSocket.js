import { useEffect, useRef, useState, useCallback } from 'react';

// Shared WebSocket hook for the realtime event stream (ws://host/ws/events).
// Auto-reconnects with backoff. Exposes connected flag, recent event ring buffer,
// and a subscribe(type, cb) for targeted listeners.
const MAX_BUFFER = 100;

export function useWebSocket() {
  const [connected, setConnected] = useState(false);
  const [events, setEvents] = useState([]);
  const wsRef = useRef(null);
  const subsRef = useRef({});
  const retryRef = useRef(0);
  const closedRef = useRef(false);

  const connect = useCallback(() => {
    if (closedRef.current) return;
    const proto = window.location.protocol === 'https:' ? 'wss' : 'ws';
    const ws = new WebSocket(`${proto}://${window.location.host}/ws/events`);
    wsRef.current = ws;
    ws.onopen = () => { setConnected(true); retryRef.current = 0; };
    ws.onmessage = (e) => {
      let msg;
      try { msg = JSON.parse(e.data); } catch { return; }
      setEvents((prev) => {
        const next = [...prev, msg];
        return next.length > MAX_BUFFER ? next.slice(next.length - MAX_BUFFER) : next;
      });
      const subs = subsRef.current[msg.type] || [];
      subs.forEach((cb) => { try { cb(msg); } catch {} });
      const any = subsRef.current['*'] || [];
      any.forEach((cb) => { try { cb(msg); } catch {} });
    };
    ws.onclose = () => {
      setConnected(false);
      if (closedRef.current) return;
      const delay = Math.min(1000 * 2 ** retryRef.current, 15000);
      retryRef.current += 1;
      setTimeout(connect, delay);
    };
    ws.onerror = () => { try { ws.close(); } catch {} };
  }, []);

  useEffect(() => {
    closedRef.current = false;
    connect();
    return () => { closedRef.current = true; try { wsRef.current?.close(); } catch {} };
  }, [connect]);

  const subscribe = useCallback((type, cb) => {
    (subsRef.current[type] = subsRef.current[type] || []).push(cb);
    return () => {
      subsRef.current[type] = (subsRef.current[type] || []).filter((f) => f !== cb);
    };
  }, []);

  return { connected, events, subscribe };
}