// Tareas asignadas, en LISTA o TABLERO, con semáforo. Desde el 05/11/2026 (fase 1 de la unificación) se muestra en
// dos vistas según el rol: «Asignado a mí» (ámbito `para-mi`: «Todas» / «Para hoy», y debajo las tareas asignadas
// desde listas compartidas, que llegan en `otras`) y «Asignadas por mí» (ámbito `por-mi`, lo que yo asigné).
import { useCallback, useEffect, useState } from 'react';
import { tareasApi } from './api';
import { AsignarTareaDialogo } from './AsignarTareaDialogo';
import { IcoLista, IcoTablero, Punto } from './IconosSeguimiento';
import { TableroKanban } from './TableroKanban';
import { TareasArchivadas } from './TareasArchivadas';
import { TareaDetalle } from './TareaDetalle';
import { TarjetaTarea } from './TarjetaTarea';
import type { Estado, Tarea } from './tipos';

type Pestana = 'mis' | 'por-mi' | 'mi-dia';
export type Ambito = 'para-mi' | 'por-mi';
interface Props {
  yo: string; tareaInicial?: string | null; ambito?: Ambito;
  /** Se llama cuando ya se abrió `tareaInicial` (para no volver a abrirla al cambiar de vista). */
  onTareaInicialAbierta?: () => void;
  /** «Asignado a mí»: tras asignar una tarea, ir a «Asignadas por mí». */
  onAsignada?: () => void;
}
const TITULO: Record<Ambito, string> = { 'para-mi': 'Asignado a mí', 'por-mi': 'Asignadas por mí' };
const tab = (activa: boolean): React.CSSProperties => ({ padding: '8px 14px', border: 'none', background: 'none', cursor: 'pointer', fontSize: 14, fontWeight: activa ? 700 : 400, color: activa ? '#0078d4' : '#323130', borderBottom: activa ? '3px solid #0078d4' : '3px solid transparent' });

export function SeguimientoVista({ yo, tareaInicial, ambito = 'para-mi', onTareaInicialAbierta, onAsignada }: Props) {
  const [pestana, setPestana] = useState<Pestana>(ambito === 'por-mi' ? 'por-mi' : 'mis');
  // Se abre en Tablero; si la persona elige Lista, se recuerda (clave nueva: la vieja guardaba «lista» a todos).
  const [modo, setModo] = useState<'lista' | 'tablero'>(() => { try { return localStorage.getItem('seguimiento.modo') === 'lista' ? 'lista' : 'tablero'; } catch { return 'tablero'; } });
  useEffect(() => { try { localStorage.setItem('seguimiento.modo', modo); } catch { /* sin almacenamiento: vuelve a Tablero */ } }, [modo]);
  // Las completadas se quedan en el tablero (trazabilidad) hasta quitarlas o a los 30 días; entonces, en «Archivadas».
  const [archivadas, setArchivadas] = useState(false);
  const [tareas, setTareas] = useState<Tarea[]>([]);
  const [cargando, setCargando] = useState(false);
  const [sel, setSel] = useState<Tarea | null>(null);
  const [asignando, setAsignando] = useState(false);

  const cargar = useCallback(async () => {
    setCargando(true);
    try {
      const r = pestana === 'mis' ? await tareasApi.mis(true) : pestana === 'por-mi' ? await tareasApi.asignadasPorMi(true) : await tareasApi.miDia();
      setTareas(r);
      setSel(s => (s ? r.find(t => t.id === s.id) || s : s));
    } catch { setTareas([]); }
    finally { setCargando(false); }
  }, [pestana]);

  useEffect(() => { cargar(); }, [cargar]);
  useEffect(() => {
    const h = () => cargar();
    window.addEventListener('refresh-tareas', h); window.addEventListener('refresh-tasks', h);
    const iv = window.setInterval(cargar, 60000);
    return () => { window.removeEventListener('refresh-tareas', h); window.removeEventListener('refresh-tasks', h); window.clearInterval(iv); };
  }, [cargar]);
  useEffect(() => {
    if (tareaInicial) tareasApi.obtener(tareaInicial).then(setSel).catch(() => {}).finally(() => onTareaInicialAbierta?.());
  }, [tareaInicial, onTareaInicialAbierta]);
  useEffect(() => { try { localStorage.setItem('tareas.modo', modo); } catch { /* sin almacenamiento: el modo no se recuerda */ } }, [modo]);

  const cambiarEstado = async (t: Tarea, estado: Estado) => {
    try { const n = estado === 'completada' ? await tareasApi.completar(t.id) : await tareasApi.estado(t.id, estado); setTareas(p => p.map(x => x.id === n.id ? n : x)); }
    catch (e) { alert(e instanceof Error && e.message ? e.message : 'No se pudo cambiar el estado'); }
  };
  const avisar = useCallback((m: string) => alert(m), []);
  // Quitar del tablero (no borra): se van de la vista al instante; si el servidor falla, se recarga.
  const quitar = async (ids: string[]) => {
    if (ids.length > 1 && !confirm(`¿Quitar del tablero las ${ids.length} tareas completadas? No se borran: quedan en «Archivadas».`)) return;
    setTareas(p => p.filter(t => !ids.includes(t.id)));
    try { await tareasApi.archivar(ids); }
    catch (e) { await cargar(); avisar('No se pudieron quitar del tablero: ' + (e instanceof Error ? e.message : '')); }
  };
  const quitarUna = { texto: 'Quitar del tablero', titulo: 'No se borra: queda en «Archivadas»', onClick: (t: Tarea) => quitar([t.id]) };
  const verArchivadas = archivadas && pestana !== 'mi-dia';
  const resumen = { rojo: tareas.filter(t => t.semaforo === 'rojo').length, amarillo: tareas.filter(t => t.semaforo === 'amarillo').length };

  return (
    <div style={{ display: 'flex', flex: 1, height: '100%', overflow: 'hidden' }}>
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        <h2 style={{ margin: 0, padding: '16px 24px 0', fontSize: 20, fontWeight: 600, color: '#323130' }}>{TITULO[ambito]}</h2>
        <div style={{ display: 'flex', alignItems: 'center', gap: 4, padding: '8px 24px 0', borderBottom: '1px solid #edebe9', flexWrap: 'wrap' }}>
          {ambito === 'para-mi' && <>
            <button style={tab(pestana === 'mis')} onClick={() => setPestana('mis')}>Todas</button>
            <button style={tab(pestana === 'mi-dia')} onClick={() => setPestana('mi-dia')}>Para hoy</button>
          </>}
          <span style={{ flex: 1 }} />
          {resumen.rojo > 0 && <span style={{ fontSize: 12, color: '#d13438', fontWeight: 600, marginRight: 8 }}><Punto color="#d13438" />{resumen.rojo} vencida{resumen.rojo > 1 ? 's' : ''}/hoy</span>}
          {resumen.amarillo > 0 && <span style={{ fontSize: 12, color: '#c19c00', fontWeight: 600, marginRight: 8 }}><Punto color="#c19c00" />{resumen.amarillo} pronto</span>}
          {pestana !== 'mi-dia' && (
            <button onClick={() => { if (archivadas) void cargar(); setArchivadas(!archivadas); }} aria-pressed={archivadas} title="Completadas que quitaste del tablero o con más de 30 días"
              style={{ ...tab(archivadas), padding: '6px 8px', borderBottom: 'none', marginRight: 4 }}>
              {archivadas ? '← Volver al tablero' : 'Archivadas'}
            </button>
          )}
          <button onClick={() => setModo('lista')} title="Lista" style={{ ...tab(modo === 'lista'), padding: '6px 8px', borderBottom: 'none', display: 'inline-flex', alignItems: 'center', gap: 5 }}><IcoLista />Lista</button>
          <button onClick={() => setModo('tablero')} title="Tablero" style={{ ...tab(modo === 'tablero'), padding: '6px 8px', borderBottom: 'none', display: 'inline-flex', alignItems: 'center', gap: 5 }}><IcoTablero />Tablero</button>
          <button onClick={() => setAsignando(true)} style={{ padding: '7px 14px', border: 'none', background: '#0078d4', color: '#fff', borderRadius: 4, cursor: 'pointer', fontWeight: 600, marginLeft: 8 }}>+ Asignar tarea</button>
        </div>
        <div style={{ flex: 1, overflowY: 'auto', paddingTop: 8 }}>
          {verArchivadas ? <TareasArchivadas key={pestana} pestana={pestana === 'mis' ? 'mis' : 'por-mi'} onAbrir={setSel} onError={avisar} />
            : cargando && !tareas.length ? <div style={{ padding: 40, textAlign: 'center', color: '#605e5c' }}>Cargando…</div>
            : !tareas.length ? (<div style={{ padding: 40, textAlign: 'center', color: '#605e5c' }}>{pestana === 'por-mi' ? 'Aún no has asignado tareas. Usa «+ Asignar tarea» o «Asignar como tarea» en un correo.' : 'Nada pendiente por aquí.'}</div>)
            : modo === 'tablero' ? <TableroKanban tareas={tareas} onAbrir={setSel} onCambiarEstado={cambiarEstado} onQuitar={quitar} />
            : tareas.map(t => <TarjetaTarea key={t.id} tarea={t} onAbrir={setSel} accion={t.estado === 'completada' ? quitarUna : undefined} />)}
        </div>
      </div>
      {sel && <TareaDetalle tarea={sel} yo={yo} onCerrar={() => setSel(null)} onCambio={t => { if (t) { setSel(t); setTareas(p => p.map(x => x.id === t.id ? t : x)); } else cargar(); }} />}
      <AsignarTareaDialogo abierto={asignando} onCerrar={() => setAsignando(false)} onCreada={() => { if (ambito === 'por-mi') cargar(); else onAsignada?.(); }} />
    </div>
  );
}
