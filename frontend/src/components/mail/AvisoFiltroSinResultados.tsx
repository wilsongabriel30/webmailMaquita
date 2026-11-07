/**
 * AvisoFiltroSinResultados.tsx — 05/11/2026.
 * La pestaña «No leídos» o «Marcados» dejó la lista vacía. Caso real: una usuaria buscó
 * «DANIEL ANCHUNDIA» con «No leídos» activo, vio «Sugerencias para afinar la búsqueda» y creyó que el
 * buscador no funcionaba; sin el filtro había 2.329 resultados. Aquí se le dice que el filtro está
 * puesto y se le ofrece «Ver todos» (con el total sin filtro si llega en menos de 2 s).
 */
import { useEffect, useState } from 'react';
import { api } from '../../api/client';
import { useMailStore } from '../../store/mailStore';

interface Props {
  filtro: 'unread' | 'flagged';
  consulta: string;
  carpeta: string;           // nombre IMAP de la carpeta actual (p. ej. INBOX, Virtual.Todo)
  buscarEnContenido: boolean;
}

const ESPERA_TOTAL_MS = 2000;

/** Total de la misma búsqueda sin el filtro de pestaña; null si tarda más de 2 s o falla. */
async function totalSinFiltro(carpeta: string, consulta: string, buscarEnContenido: boolean): Promise<number | null> {
  const p = new URLSearchParams({ page: '1', per_page: '1', search: consulta });
  if (buscarEnContenido) p.set('buscar_en_contenido', 'true');
  const peticion = api.get<{ total?: number }>(`/mail/messages/${encodeURIComponent(carpeta)}?${p}`)
    .then((r) => (typeof r?.total === 'number' ? r.total : null))
    .catch(() => null);
  const espera = new Promise<null>((resolve) => setTimeout(() => resolve(null), ESPERA_TOTAL_MS));
  return Promise.race([peticion, espera]);
}

export function AvisoFiltroSinResultados({ filtro, consulta, carpeta, buscarEnContenido }: Props) {
  const setFilter = useMailStore((s) => s.setFilter);
  const busqueda = `${carpeta}\n${consulta}\n${buscarEnContenido}`;
  const [resultado, setResultado] = useState<{ busqueda: string; total: number | null }>({ busqueda: '', total: null });
  const total = resultado.busqueda === busqueda ? resultado.total : null;
  const hayBusqueda = consulta.trim().length > 0;
  const queFiltra = filtro === 'unread' ? 'no leídos' : 'marcados con bandera';

  useEffect(() => {
    if (!hayBusqueda) return;
    let vivo = true;
    totalSinFiltro(carpeta, consulta, buscarEnContenido).then((t) => { if (vivo) setResultado({ busqueda, total: t }); });
    return () => { vivo = false; };
  }, [carpeta, consulta, buscarEnContenido, hayBusqueda, busqueda]);

  const texto = hayBusqueda
    ? `Estás viendo solo los correos ${queFiltra}. Puede que el correo que buscas ya esté ${filtro === 'unread' ? 'leído' : 'sin bandera'}.`
    : `No tienes correos ${queFiltra} en esta carpeta.`;
  const etiquetaBoton = total && total > 0 ? `Ver todos (${total.toLocaleString('es-EC')})` : 'Ver todos';

  return (
    <div className="mx-4 mb-3 px-3 py-2 rounded border border-[#f0e6b8] bg-[#fff4ce] text-[13px] text-[#323130] text-left max-w-[420px]">
      <p>{texto}</p>
      <button
        type="button"
        onClick={() => setFilter('all')}
        className="mt-1 text-[13px] font-semibold text-[#0078d4] hover:underline"
      >
        {etiquetaBoton}
      </button>
    </div>
  );
}
