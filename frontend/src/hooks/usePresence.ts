import { useState, useEffect, useCallback } from 'react';

export interface UserPresence {
  email: string;
  status: 'online' | 'busy' | 'away' | 'offline';
  custom_message?: string;
  last_seen?: string;
}

let wsInstance: WebSocket | null = null;
let heartbeatTimer: ReturnType<typeof setInterval> | null = null;
const listeners = new Set<(users: Record<string, UserPresence>) => void>();
let presenceCache: Record<string, UserPresence> = {};

function connectPresenceWS() {
  if (wsInstance && wsInstance.readyState <= 1) return;
  const proto = location.protocol === 'https:' ? 'wss' : 'ws';
  wsInstance = new WebSocket(`${proto}://${location.host}/api/presence/ws`);
  wsInstance.onmessage = (ev) => {
    try {
      const data = JSON.parse(ev.data);
      if (data.email) {
        presenceCache[data.email] = data;
        listeners.forEach(fn => fn({ ...presenceCache }));
      }
    } catch {}
  };
  wsInstance.onclose = () => { setTimeout(connectPresenceWS, 5000); };
}

function startHeartbeat() {
  if (heartbeatTimer) return;
  // Initial status set
  fetch('/api/presence/status', {
    method: 'PUT', credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ status: 'online' }),
  }).catch(() => {});
  heartbeatTimer = setInterval(() => {
    fetch('/api/presence/heartbeat', { method: 'POST', credentials: 'include' }).catch(() => {});
  }, 60000);
}

export function usePresence() {
  const [users, setUsers] = useState<Record<string, UserPresence>>(presenceCache);

  useEffect(() => {
    const handler = (u: Record<string, UserPresence>) => setUsers(u);
    listeners.add(handler);
    connectPresenceWS();
    startHeartbeat();

    // Load initial
    fetch('/api/presence/users', { credentials: 'include' })
      .then(r => r.json())
      .then((list: UserPresence[]) => {
        list.forEach(u => { presenceCache[u.email] = u; });
        setUsers({ ...presenceCache });
      }).catch(() => {});

    return () => { listeners.delete(handler); };
  }, []);

  const setStatus = useCallback((status: string, message?: string) => {
    fetch('/api/presence/status', {
      method: 'PUT', credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status, custom_message: message }),
    }).catch(() => {});
  }, []);

  return { users, setStatus };
}

export function useUserPresence(email?: string): UserPresence | null {
  const { users } = usePresence();
  if (!email) return null;
  return users[email] || null;
}
