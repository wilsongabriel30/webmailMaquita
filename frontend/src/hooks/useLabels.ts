import { useState, useEffect, useCallback } from 'react';
import { api } from '../api/client';

export interface Label {
  id: number;
  name: string;
  color: string;
  count?: number;
}

export const LABEL_COLORS = [
  { value: '#d13438', name: 'Rojo' },
  { value: '#0078d4', name: 'Azul' },
  { value: '#107c10', name: 'Verde' },
  { value: '#ca5010', name: 'Naranja' },
  { value: '#8764b8', name: 'Morado' },
  { value: '#038387', name: 'Teal' },
  { value: '#c239b3', name: 'Rosa' },
  { value: '#69797e', name: 'Gris' },
];

let _labels: Label[] = [];
let _listeners: Set<() => void> = new Set();
let _supported: boolean | null = null;

function notify() {
  _listeners.forEach(fn => fn());
}

export function getCachedLabels() {
  return [..._labels];
}

export function useLabels() {
  const [labels, setLabels] = useState<Label[]>(_labels);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const listener = () => setLabels([..._labels]);
    _listeners.add(listener);
    return () => { _listeners.delete(listener); };
  }, []);

  const fetchLabels = useCallback(async () => {
    if (_supported === false) {
      setLoading(false);
      return [];
    }
    setLoading(true);
    try {
      const res = await api.get<{ labels: Label[] }>('/mail/labels');
      _labels = res.labels;
      _supported = true;
      notify();
      return res.labels;
    } catch (error) {
      // Some deployed servers still do not expose `/mail/labels`.
      // Treating 404 as "unsupported" avoids noisy requests and unrelated UI regressions.
      if (error instanceof Error && (error.message === 'HTTP 404' || error.message === 'Not Found')) {
        _labels = [];
        _supported = false;
        notify();
        return [];
      }
      return [];
    } finally {
      setLoading(false);
    }
  }, []);

  // Listen for label refresh events
  useEffect(() => {
    const handler = () => {
      if (_supported === false) return;
      fetchLabels();
    };
    window.addEventListener('refresh-labels', handler);
    return () => window.removeEventListener('refresh-labels', handler);
  }, [fetchLabels]);

  const createLabel = useCallback(async (name: string, color: string) => {
    if (_supported === false) throw new Error('Etiquetas no disponibles');
    const res = await api.post<Label>('/mail/labels', { name, color });
    await fetchLabels();
    return res;
  }, [fetchLabels]);

  const updateLabel = useCallback(async (id: number, data: { name?: string; color?: string }) => {
    if (_supported === false) throw new Error('Etiquetas no disponibles');
    const res = await api.put<Label>(`/mail/labels/${id}`, data);
    await fetchLabels();
    return res;
  }, [fetchLabels]);

  const deleteLabel = useCallback(async (id: number) => {
    if (_supported === false) throw new Error('Etiquetas no disponibles');
    await api.del(`/mail/labels/${id}`);
    await fetchLabels();
  }, [fetchLabels]);

  const assignLabel = useCallback(async (labelId: number, folder: string, uids: number[]) => {
    if (_supported === false) throw new Error('Etiquetas no disponibles');
    await api.post(`/mail/labels/${labelId}/assign`, { folder, uids });
    window.dispatchEvent(new CustomEvent('refresh-message-labels'));
    await fetchLabels();
  }, [fetchLabels]);

  const unassignLabel = useCallback(async (labelId: number, folder: string, uids: number[]) => {
    if (_supported === false) throw new Error('Etiquetas no disponibles');
    await api.post(`/mail/labels/${labelId}/unassign`, { folder, uids });
    window.dispatchEvent(new CustomEvent('refresh-message-labels'));
    await fetchLabels();
  }, [fetchLabels]);

  return { labels, loading, supported: _supported !== false, fetchLabels, createLabel, updateLabel, deleteLabel, assignLabel, unassignLabel };
}

export function useMessageLabels(folder: string, uids: number[]) {
  const [msgLabels, setMsgLabels] = useState<Record<string, Label[]>>({});

  const fetchMsgLabels = useCallback(async () => {
    if (!folder || !uids.length) { setMsgLabels({}); return; }
    try {
      const uidStr = uids.join(',');
      const res = await api.get<{ message_labels: Record<string, Label[]> }>(`/mail/labels/messages/${encodeURIComponent(folder)}?uids=${encodeURIComponent(uidStr)}`);
      setMsgLabels(res.message_labels);
    } catch { setMsgLabels({}); }
  }, [folder, uids.join(',')]);

  useEffect(() => { fetchMsgLabels(); }, [fetchMsgLabels]);

  useEffect(() => {
    const handler = () => fetchMsgLabels();
    window.addEventListener('refresh-message-labels', handler);
    return () => window.removeEventListener('refresh-message-labels', handler);
  }, [fetchMsgLabels]);

  return msgLabels;
}
