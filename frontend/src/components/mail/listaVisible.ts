/**
 * listaVisible.ts — Lista visible y resaltado por UID (05/11/2026).
 *
 * La lista que ve la persona (`filtered` en MessageList) no es `messages` del store: la pestaña
 * «Otros» quita correos y las chinchetas reordenan. Los atajos de teclado (flechas, Enter, Supr)
 * navegaban `messages[activeIndex]`, así que podían abrir o BORRAR el correo de al lado.
 * Además, al llegar un correo nuevo (sondeo cada 45 s) el índice resaltado señalaba otro correo.
 *
 * Este hook publica en el store los UIDs visibles en su orden real y, cuando la lista cambia,
 * recoloca el resaltado sobre el MISMO UID que estaba resaltado.
 */
import { useEffect } from 'react';
import { useMailStore } from '../../store/mailStore';
import type { MessageSummary } from '../../types';

export function usePublicarListaVisible(filtered: MessageSummary[]) {
  const ids = filtered.map(m => m.uid).join(',');
  useEffect(() => {
    const st = useMailStore.getState();
    const uids = ids ? ids.split(',').map(Number) : [];
    let indice = st.activeIndex;
    if (st.activeUid !== null) {
      const i = uids.indexOf(st.activeUid);
      if (i >= 0) indice = i;                               // el mismo correo, en su nueva posición
      else if (indice >= uids.length) indice = uids.length - 1; // ya no está: se queda en el último
    } else if (indice >= uids.length) {
      indice = uids.length - 1;
    }
    st.setVisibleUids(uids, indice);
  }, [ids]);
}
