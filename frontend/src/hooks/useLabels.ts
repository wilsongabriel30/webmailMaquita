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
let _loaded = false;

function notify() {
  _listeners.forEach(fn => fn());
}

export function useLabels() {
  const [labels, setLabels] = useState<Label[]>(_labels);
  const [loading, setLoading] = useState(!_loaded);

  useEffect(() => {
    const listener = () => setLabels([..._labels]);
    _listeners.add(listener);
    return () => { _listeners.delete(listener); };
  }, []);

  const fetchLabels = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.get<{ labels: Label[] }>('/mail/labels');
      _labels = res.labels;
      _loaded = true;
      notify();
    } catch {}
    setLoading(false);
  }, []);

  useEffect(() => {
    if (!_loaded) fetchLabels();
  }, [fetchLabels]);

  // Listen for label refresh events
  useEffect(() => {
    const handler = () => fetchLabels();
    window.addEventListener('refresh-labels', handler);
    return () => window.removeEventListener('refresh-labels', handler);
  }, [fetchLabels]);

  const createLabel = useCallback(async (name: string, color: string) => {
    const res = await api.post<Label>('/mail/labels', { name, color });
    await fetchLabels();
    return res;
  }, [fetchLabels]);

  const updateLabel = useCallback(async (id: number, data: { name?: string; color?: string }) => {
    const res = await api.put<Label>(, data);
    await fetchLabels();
    return res;
  }, [fetchLabels]);

  const deleteLabel = useCallback(async (id: number) => {
    await api.del();
    await fetchLabels();
  }, [fetchLabels]);

  const assignLabel = useCallback(async (labelId: number, folder: string, uids: number[]) => {
    await api.post(, { folder, uids });
    window.dispatchEvent(new CustomEvent('refresh-message-labels'));
    await fetchLabels();
  }, [fetchLabels]);

  const unassignLabel = useCallback(async (labelId: number, folder: string, uids: number[]) => {
    await api.post(, { folder, uids });
    window.dispatchEvent(new CustomEvent('refresh-message-labels'));
    await fetchLabels();
  }, [fetchLabels]);

  return { labels, loading, fetchLabels, createLabel, updateLabel, deleteLabel, assignLabel, unassignLabel };
}

export function useMessageLabels(folder: string, uids: number[]) {
  const [msgLabels, setMsgLabels] = useState<Record<string, Label[]>>({});

  const fetchMsgLabels = useCallback(async () => {
    if (!folder || !uids.length) { setMsgLabels({}); return; }
    try {
      const uidStr = uids.join(',');
      const res = await api.get<{ message_labels: Record<string, Label[]> }>(
        
      );
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
