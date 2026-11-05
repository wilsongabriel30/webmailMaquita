import { useState, useEffect } from 'react';
import { api } from '../../api/client';
import { showToast } from './Toast';
import { abrirReunion, enlaceReunionSeguro, quitarLineaEnlace } from '../../lib/enlaceReunion';
import { TarjetaAviso, type DatosTarea } from './TarjetaAviso';

interface Rem {
  id: string;
  message: string;
  kind?: string;
  entityId?: string;
  enlace?: string;
  tarea?: DatosTarea | null;
}

interface TareaVista { id: string; title: string; due_date?: string | null; reminder?: string | null }

/** El servidor manda «⏰ Recordatorio de tarea: <título>»; el título solo, por si no se encuentra la tarea. */
const tituloDelMensaje = (m: string) => m.replace(/^\s*⏰?\s*Recordatorio de tarea:\s*/u, '').trim() || m;

function posponerHasta(minutos: number): string {
  if (minutos > 0) return new Date(Date.now() + minutos * 60000).toISOString();
  const d = new Date();
  d.setDate(d.getDate() + 1);
  d.setHours(9, 0, 0, 0);
  return d.toISOString();
}

/** Avisos de recordatorio persistentes, arriba a la derecha bajo la barra, como en Outlook (TarjetaAviso).
 *  Se alimentan del evento global 'show-reminder' (WebSocket type=reminder). Van por delante de la burbuja del chat. */
export function ReminderPopup() {
  const [items, setItems] = useState<Rem[]>([]);

  useEffect(() => {
    const h = (e: Event) => {
      const d = (e as CustomEvent).detail || {};
      const id = d.tag || `rem-${Math.random().toString(36).slice(2)}`;
      const nuevo: Rem = { id, message: d.message || 'Recordatorio', kind: d.kind, entityId: d.entity_id, enlace: enlaceReunionSeguro(d.link) };
      if (nuevo.kind === 'task') nuevo.tarea = { titulo: tituloDelMensaje(nuevo.message) };
      setItems(prev => prev.some(p => p.id === id) ? prev : [...prev, nuevo]);
      // Vencimiento y recordatorio de la tarea (segunda línea del aviso): «Planeado» trae las que tienen recordatorio.
      if (nuevo.kind === 'task' && nuevo.entityId) {
        api.get<TareaVista[]>('/tasks/views/planned').then(lista => {
          const t = lista.find(x => x.id === nuevo.entityId);
          if (!t) return;
          setItems(prev => prev.map(p => p.id === id
            ? { ...p, tarea: { titulo: t.title, vence: t.due_date, recordatorio: t.reminder } } : p));
        }).catch(() => { /* sin la segunda línea: el aviso sigue sirviendo */ });
      }
    };
    window.addEventListener('show-reminder', h);
    return () => window.removeEventListener('show-reminder', h);
  }, []);

  const cerrar = (id: string) => setItems(prev => prev.filter(p => p.id !== id));

  const posponer = async (r: Rem, minutos: number) => {
    try {
      await api.patch(`/tasks/tasks/${r.entityId}`, { reminder: posponerHasta(minutos) });
      showToast(minutos > 0 ? `Aviso pospuesto ${minutos >= 60 ? `${minutos / 60} hora${minutos > 60 ? 's' : ''}` : `${minutos} minutos`}` : 'Aviso pospuesto hasta mañana a las 9:00');
      window.dispatchEvent(new CustomEvent('refresh-tasks'));
    } catch {
      showToast('No se pudo posponer el aviso');
    }
    cerrar(r.id);
  };

  const completar = async (r: Rem) => {
    try {
      await api.patch(`/tasks/tasks/${r.entityId}/toggle`);
      showToast('Tarea completada');
      window.dispatchEvent(new CustomEvent('refresh-tasks'));
      cerrar(r.id);
    } catch {
      showToast('No se pudo completar la tarea');
    }
  };

  if (items.length === 0) return null;

  return (
    <div className="fixed top-[56px] right-3 z-[10000] flex flex-col gap-2 w-[480px] max-w-[calc(100vw-24px)] max-h-[calc(100vh-72px)] overflow-y-auto">
      {items.map(r => (
        <TarjetaAviso key={r.id} tipo={r.kind}
          texto={quitarLineaEnlace(r.message, r.enlace || '')}
          tarea={r.tarea}
          enlace={r.enlace}
          onCompletar={r.kind === 'task' && r.entityId ? () => completar(r) : undefined}
          onPosponer={r.kind === 'task' && r.entityId ? m => posponer(r, m) : undefined}
          onEntrar={r.enlace ? () => { abrirReunion(r.enlace!); cerrar(r.id); } : undefined}
          onCerrar={() => cerrar(r.id)} />
      ))}
    </div>
  );
}
