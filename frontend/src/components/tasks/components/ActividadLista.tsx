// Registro de actividad (de una lista o de una tarea): quién hizo qué y cuándo, lo más reciente primero.
import { useEffect, useState } from 'react';
import { api } from '../../../api/client';
import type { EventoActividad } from '../types';
import { COLORS } from '../types';
import { CirculoPersona } from './CirculoPersona';

function cuando(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleDateString('es-ES', { day: 'numeric', month: 'short' }) + ' ' + d.toLocaleTimeString('es-ES', { hour: '2-digit', minute: '2-digit' });
}

export function ActividadLista({ ruta, vacio = 'Todavía no hay actividad.' }: { ruta: string; vacio?: string }) {
  const [eventos, setEventos] = useState<EventoActividad[] | null>(null);
  useEffect(() => {
    let vigente = true;
    api.get<EventoActividad[]>(ruta)
      .catch(() => [] as EventoActividad[])
      .then(e => { if (vigente) setEventos(e); });
    return () => { vigente = false; };
  }, [ruta]);

  if (eventos === null) return <div style={{ fontSize: 12, color: COLORS.secondary, padding: 8 }}>Cargando…</div>;
  if (eventos.length === 0) return <div style={{ fontSize: 12, color: COLORS.secondary, padding: 8 }}>{vacio}</div>;
  return (
    <ul style={{ listStyle: 'none', margin: 0, padding: 0 }}>
      {eventos.map((e, i) => (
        <li key={i} style={{ display: 'flex', gap: 8, padding: '6px 0', fontSize: 12, color: COLORS.text }}>
          <CirculoPersona email={e.user_email} nombre={e.nombre} tamano={22} />
          <div style={{ minWidth: 0 }}>
            <div><strong>{e.nombre}</strong> · {e.details}</div>
            <div style={{ color: COLORS.secondary }}>{cuando(e.created_at)}</div>
          </div>
        </li>
      ))}
    </ul>
  );
}
