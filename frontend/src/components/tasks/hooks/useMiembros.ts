// Personas de una lista (propietaria y miembros). Se vuelve a pedir cuando cambia la lista o tras compartir.
import { useCallback, useEffect, useState } from 'react';
import { api } from '../../../api/client';
import type { MiembroLista } from '../types';

export function useMiembros(listId: string | null | undefined) {
  const [miembros, setMiembros] = useState<MiembroLista[]>([]);
  const [version, setVersion] = useState(0);

  useEffect(() => {
    if (!listId) return;
    let vigente = true;
    api.get<MiembroLista[]>(`/tasks/lists/${listId}/miembros`)
      .catch(() => [] as MiembroLista[])
      .then(m => { if (vigente) setMiembros(m); });
    return () => { vigente = false; };
  }, [listId, version]);

  const recargar = useCallback(() => setVersion(v => v + 1), []);
  return { miembros: listId ? miembros : [], recargar };
}
