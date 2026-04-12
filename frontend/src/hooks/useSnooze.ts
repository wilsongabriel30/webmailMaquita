import { useState, useCallback } from 'react';
import { api } from '../api/client';

export interface SnoozedEmail {
  id: number;
  original_folder: string;
  original_uid: number;
  snooze_until: string;
  subject: string;
  from_addr: string;
  created_at: string;
}

export function useSnooze() {
  const [snoozed, setSnoozed] = useState<SnoozedEmail[]>([]);
  const [loading, setLoading] = useState(false);

  const snoozeEmail = useCallback(async (folder: string, uid: number, snoozeUntil: Date) => {
    const res = await api.post<{ id: number }>('/mail/snooze', {
      folder,
      uid,
      snooze_until: snoozeUntil.toISOString(),
    });
    window.dispatchEvent(new CustomEvent('refresh-messages'));
    return res;
  }, []);

  const cancelSnooze = useCallback(async (id: number) => {
    await api.del(`/mail/snooze/${id}`);
    window.dispatchEvent(new CustomEvent('refresh-messages'));
    setSnoozed((prev) => prev.filter((s) => s.id !== id));
  }, []);

  const listSnoozed = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.get<{ snoozed: SnoozedEmail[] }>('/mail/snooze');
      setSnoozed(res.snoozed);
      return res.snoozed;
    } catch {
      return [];
    } finally {
      setLoading(false);
    }
  }, []);

  return { snoozed, loading, snoozeEmail, cancelSnooze, listSnoozed };
}
