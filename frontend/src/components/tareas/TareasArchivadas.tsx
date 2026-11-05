// «Archivadas» de Seguimiento (05/11/2026): las completadas que la persona quitó de su tablero o que llevan más de
// 30 días completadas. No se borran: aquí se consultan con su historial y se pueden devolver al tablero.
// Cada persona tiene las suyas (archivar no le quita la tarea a nadie más).
import { useCallback, useEffect, useState } from 'react';
import { tareasApi } from './api';
import type { Tarea } from './tipos';
import { TarjetaTarea } from './TarjetaTarea';

interface Props {
  /** «mis»: las que me asignaron; «por-mi»: las que asigné. */
  pestana: 'mis' | 'por-mi';
  onAbrir: (t: Tarea) => void;
  onError: (mensaje: string) => void;
}

export function TareasArchivadas({ pestana, onAbrir, onError }: Props) {
  const [tareas, setTareas] = useState<Tarea[] | null>(null);

  const cargar = useCallback(() => {
    const pedir = pestana === 'mis' ? tareasApi.mis(true, true) : tareasApi.asignadasPorMi(true, true);
    pedir.then(setTareas).catch(e => { setTareas([]); onError('No se pudieron cargar las archivadas: ' + (e instanceof Error ? e.message : '')); });
  }, [pestana, onError]);
  useEffect(() => { cargar(); }, [cargar]);

  const devolver = async (t: Tarea) => {
    setTareas(p => (p || []).filter(x => x.id !== t.id));
    try { await tareasApi.restaurar(t.id); }
    catch (e) { onError('No se pudo devolver al tablero: ' + (e instanceof Error ? e.message : '')); cargar(); }
  };

  if (tareas === null) return <div style={{ padding: 40, textAlign: 'center', color: '#605e5c' }}>Cargando…</div>;
  return (
    <div>
      <p style={{ margin: '4px 24px 8px', fontSize: 13, color: '#605e5c' }}>
        Completadas que quitaste del tablero o que llevan más de 30 días completadas. No se borran: siguen con su historial.
      </p>
      {!tareas.length
        ? <div style={{ padding: 40, textAlign: 'center', color: '#605e5c' }}>No hay tareas archivadas.</div>
        : tareas.map(t => (
          <TarjetaTarea key={t.id} tarea={t} onAbrir={onAbrir}
            accion={{ texto: 'Devolver al tablero', titulo: 'Vuelve a la columna «Completada»', onClick: devolver }} />
        ))}
    </div>
  );
}
