import { useState, useCallback } from 'react';
import { api } from '../api/client';

export interface PriorityData {
  [uid: number]: {
    priority: 'high' | 'normal' | 'low';
    category: string;
    reason: string;
  };
}

export function usePriority() {
  const [priorityMap, setPriorityMap] = useState<PriorityData>({});
  const [loading, setLoading] = useState(false);

  const fetchPriority = useCallback(async (folder: string) => {
    if (folder !== 'INBOX') return; // Solo clasificar INBOX
    setLoading(true);
    try {
      const data = await api.get<{
        high: any[];
        normal: any[];
        low: any[];
      }>(`/mail/priority?folder=${encodeURIComponent(folder)}&limit=50`);

      const map: PriorityData = {};
      for (const msg of data.high) {
        map[msg.uid] = { priority: 'high', category: msg.category || '', reason: msg.priority_reason || '' };
      }
      for (const msg of data.normal) {
        map[msg.uid] = { priority: 'normal', category: msg.category || '', reason: msg.priority_reason || '' };
      }
      for (const msg of data.low) {
        map[msg.uid] = { priority: 'low', category: msg.category || '', reason: msg.priority_reason || '' };
      }
      setPriorityMap(prev => {
        // Merge: keep existing classifications, add/update new ones
        // Never downgrade: if a message was high/normal, don't move to low automatically
        const merged = { ...prev };
        for (const [uid, data] of Object.entries(map)) {
          const numUid = Number(uid);
          const existing = merged[numUid];
          if (existing && (existing.priority === 'high' || existing.priority === 'normal') && (data as any).priority === 'low') {
            // Don't downgrade - keep existing classification
            continue;
          }
          merged[numUid] = data as any;
        }
        return merged;
      });
    } catch (err) {
      console.warn('Priority fetch failed, using default:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  const reclassify = useCallback(async (folder: string, uid: number, priority: 'high' | 'normal' | 'low') => {
    try {
      await api.post('/mail/priority/reclassify', { folder, uid, priority });
      setPriorityMap(prev => ({
        ...prev,
        [uid]: { ...prev[uid], priority, category: 'manual', reason: 'Clasificado manualmente' },
      }));
    } catch (err) {
      console.error('Reclassify failed:', err);
    }
  }, []);

  const clearCache = useCallback(async (folder: string) => {
    try {
      await api.del(`/mail/priority/cache?folder=${encodeURIComponent(folder)}`);
      setPriorityMap({});
    } catch (err) {
      console.error('Clear cache failed:', err);
    }
  }, []);

  return { priorityMap, loading, fetchPriority, reclassify, clearCache };
}
