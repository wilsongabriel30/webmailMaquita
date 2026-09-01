// Seguimiento de tareas asignadas: «Mis tareas» / «Asignadas por mí» / «Mi día», en LISTA o TABLERO, con semáforo.
import { useCallback, useEffect, useState } from 'react';
import { tareasApi } from './api';
import { AsignarTareaDialogo } from './AsignarTareaDialogo';
import { TableroKanban } from './TableroKanban';
import { TareaDetalle } from './TareaDetalle';
import { TarjetaTarea } from './TarjetaTarea';
import type { Estado, Tarea } from './tipos';

type Pestana = 'mis' | 'por-mi' | 'mi-dia';
interface Props { yo: string; tareaInicial?: string | null }
const tab = (activa: boolean): React.CSSProperties => ({ padding: '8px 14px', border: 'none', background: 'none', cursor: 'pointer', fontSize: 14, fontWeight: activa ? 700 : 400, color: activa ? '#0078d4' : '#323130', borderBottom: activa ? '3px solid #0078d4' : '3px solid transparent' });

export function SeguimientoVista({ yo, tareaInicial }: Props) {
  const [pestana, setPestana] = useState<Pestana>('mis');
  const [modo, setModo] = useState<'lista' | 'tablero'>(() => { try { return (localStorage.getItem('tareas.modo') as 'lista' | 'tablero') || 'lista'; } catch { return 'lista'; } });
  const [completadas, setCompletadas] = useState(false);
  const [tareas, setTareas] = useState<Tarea[]>([]);
  const [cargando, setCargando] = useState(false);
  const [sel, setSel] = useState<Tarea | null>(null);
  const [asignando, setAsignando] = useState(false);

  const cargar = useCallback(async () => {
    setCargando(true);
    try {
      const r = pestana === 'mis' ? await tareasApi.mis(completadas) : pestana === 'por-mi' ? await tareasApi.asignadasPorMi(completadas) : await tareasApi.miDia();
      setTareas(r);
      setSel(s => (s ? r.find(t => t.id === s.id) || s : s));
    } catch { setTareas([]); }
    finally { setCargando(false); }
  }, [pestana, completadas]);

  useEffect(() => { cargar(); }, [cargar]);
  useEffect(() => {
    const h = () => cargar();
    window.addEventListener('refresh-tareas', h); window.addEventListener('refresh-tasks', h);
    const iv = window.setInterval(cargar, 60000);
    return () => { window.removeEventListener('refresh-tareas', h); window.removeEventListener('refresh-tasks', h); window.clearInterval(iv); };
  }, [cargar]);
  useEffect(() => { if (tareaInicial) tareasApi.obtener(tareaInicial).then(setSel).catch(() => {}); }, [tareaInicial]);
  useEffect(() => { try { localStorage.setItem('tareas.modo', modo); } catch {} }, [modo]);

  const cambiarEstado = async (t: Tarea, estado: Estado) => {
    try { const n = estado === 'completada' ? await tareasApi.completar(t.id) : await tareasApi.estado(t.id, estado); setTareas(p => p.map(x => x.id === n.id ? n : x)); }
    catch (e: any) { alert(e.message || 'No se pudo cambiar el estado'); }
  };
  const resumen = { rojo: tareas.filter(t => t.semaforo === 'rojo').length, amarillo: tareas.filter(t => t.semaforo === 'amarillo').length };

  return (
    <div style={{ display: 'flex', flex: 1, height: '100%', overflow: 'hidden' }}>
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 4, padding: '8px 24px 0', borderBottom: '1px solid #edebe9', flexWrap: 'wrap' }}>
          <button style={tab(pestana === 'mis')} onClick={() => setPestana('mis')}>Mis tareas</button>
          <button style={tab(pestana === 'por-mi')} onClick={() => setPestana('por-mi')}>Asignadas por mí</button>
          <button style={tab(pestana === 'mi-dia')} onClick={() => setPestana('mi-dia')}>Mi día</button>
          <span style={{ flex: 1 }} />
          {resumen.rojo > 0 && <span style={{ fontSize: 12, color: '#d13438', fontWeight: 600, marginRight: 8 }}>● {resumen.rojo} vencida{resumen.rojo > 1 ? 's' : ''}/hoy</span>}
          {resumen.amarillo > 0 && <span style={{ fontSize: 12, color: '#c19c00', fontWeight: 600, marginRight: 8 }}>● {resumen.amarillo} pronto</span>}
          <label style={{ fontSize: 12, color: '#605e5c', marginRight: 8 }}><input type="checkbox" checked={completadas} onChange={e => setCompletadas(e.target.checked)} /> completadas</label>
          <button onClick={() => setModo('lista')} title="Lista" style={{ ...tab(modo === 'lista'), padding: '6px 8px', borderBottom: 'none' }}>☰ Lista</button>
          <button onClick={() => setModo('tablero')} title="Tablero" style={{ ...tab(modo === 'tablero'), padding: '6px 8px', borderBottom: 'none' }}>▦ Tablero</button>
          <button onClick={() => setAsignando(true)} style={{ padding: '7px 14px', border: 'none', background: '#0078d4', color: '#fff', borderRadius: 4, cursor: 'pointer', fontWeight: 600, marginLeft: 8 }}>+ Asignar tarea</button>
        </div>
        <div style={{ flex: 1, overflowY: 'auto', paddingTop: 8 }}>
          {cargando && !tareas.length ? <div style={{ padding: 40, textAlign: 'center', color: '#605e5c' }}>Cargando…</div>
            : !tareas.length ? <div style={{ padding: 40, textAlign: 'center', color: '#605e5c' }}>{pestana === 'por-mi' ? 'Aún no has asignado tareas. Usa «+ Asignar tarea» o «Asignar como tarea» en un correo.' : 'Nada pendiente por aquí. 🎉'}</div>
            : modo === 'tablero' ? <TableroKanban tareas={tareas} onAbrir={setSel} onCambiarEstado={cambiarEstado} />
            : tareas.map(t => <TarjetaTarea key={t.id} tarea={t} onAbrir={setSel} />)}
        </div>
      </div>
      {sel && <TareaDetalle tarea={sel} yo={yo} onCerrar={() => setSel(null)} onCambio={t => { if (t) { setSel(t); setTareas(p => p.map(x => x.id === t.id ? t : x)); } else cargar(); }} />}
      <AsignarTareaDialogo abierto={asignando} onCerrar={() => setAsignando(false)} onCreada={() => { setPestana('por-mi'); cargar(); }} />
    </div>
  );
}
