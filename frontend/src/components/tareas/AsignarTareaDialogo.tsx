// Diálogo «Asignar tarea»: título, descripción, asignados, plazo, prioridad, etiquetas, subtareas, recurrencia,
// cadena (se activa al completar otra) y jefe para escalamiento. Puede nacer desde un correo (queda enlazado).
// Desde la fase 2 (05/11/2026) es el ÚNICO cuadro para asignar: «Asignar tarea a:» de una tarea de lista lo abre con
// `desde` y, al guardar, esa misma tarea pasa a tener seguimiento.
import { useEffect, useState } from 'react';
import { IcoClip } from './IconosSeguimiento';
import { tareasApi } from './api';
import { SelectorPersonas } from './SelectorPersonas';
import type { Tarea } from './tipos';
import { PRIORIDAD_NOMBRE, RECURRENCIAS } from './tipos';

export interface CorreoRef { folder: string; uid: number; subject?: string; from?: string }
/** Tarea de lista que se asigna (se rellena con sus datos y se convierte en vez de crear otra). */
export interface DesdeTarea { id: string; titulo: string; descripcion?: string; plazo?: string | null; asignados?: string[] }
interface Props { abierto: boolean; onCerrar: () => void; onCreada?: (t: Tarea) => void; correo?: CorreoRef | null; tituloInicial?: string; descripcionInicial?: string; desde?: DesdeTarea | null }

/** Fecha de vencimiento de una tarea de lista (día) → campo «Plazo» (fecha y hora): ese día al final de la jornada. */
const plazoDe = (fecha?: string | null) => (fecha ? `${fecha.slice(0, 10)}T17:00` : '');

const lbl: React.CSSProperties = { fontSize: 12, fontWeight: 600, color: '#605e5c', margin: '10px 0 4px', display: 'block' };
const inp: React.CSSProperties = { width: '100%', border: '1px solid #c8c6c4', borderRadius: 4, padding: '7px 8px', fontSize: 14, boxSizing: 'border-box' };

export function AsignarTareaDialogo({ abierto, onCerrar, onCreada, correo, tituloInicial, descripcionInicial, desde }: Props) {
  const [titulo, setTitulo] = useState('');
  const [descripcion, setDescripcion] = useState('');
  const [asignados, setAsignados] = useState<string[]>([]);
  const [plazo, setPlazo] = useState('');
  const [prioridad, setPrioridad] = useState('medium');
  const [etiquetas, setEtiquetas] = useState('');
  const [subtareas, setSubtareas] = useState('');
  const [recurrencia, setRecurrencia] = useState('');
  const [enEspera, setEnEspera] = useState(false);
  const [activaTareaId, setActivaTareaId] = useState('');
  const [misAsignadas, setMisAsignadas] = useState<Tarea[]>([]);
  const [escalarA, setEscalarA] = useState<string[]>([]);
  const [masOpciones, setMasOpciones] = useState(false);
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!abierto) return;
    setTitulo(desde?.titulo || tituloInicial || (correo?.subject ? correo.subject.replace(/^(re|rv|fwd?|fw):\s*/i, '') : ''));
    setDescripcion(desde?.descripcion || descripcionInicial || (correo ? `Correo de ${correo.from || ''}: «${correo.subject || ''}»` : ''));
    setAsignados(desde?.asignados || []); setPlazo(plazoDe(desde?.plazo)); setPrioridad('medium'); setEtiquetas(''); setSubtareas(''); setRecurrencia('');
    setEnEspera(false); setActivaTareaId(''); setEscalarA([]); setMasOpciones(false); setError('');
    tareasApi.asignadasPorMi().then(setMisAsignadas).catch(() => setMisAsignadas([]));
  }, [abierto, correo, tituloInicial, descripcionInicial, desde]);

  if (!abierto) return null;

  const guardar = async () => {
    if (!titulo.trim()) { setError('Escribe el título de la tarea'); return; }
    if (!asignados.length) { setError('Elige al menos una persona'); return; }
    setGuardando(true); setError('');
    try {
      const datos = {
        titulo: titulo.trim(), descripcion, asignados, plazo: plazo ? new Date(plazo).toISOString() : null, prioridad,
        etiquetas: etiquetas.split(',').map(s => s.trim()).filter(Boolean),
        subtareas: subtareas.split('\n').map(s => s.trim()).filter(Boolean),
        recurrencia: recurrencia || null, en_espera: enEspera && !!activaTareaId, activa_tarea_id: activaTareaId || null,
        escalar_a: escalarA[0] || null, correo: correo || null,
      };
      const t = desde ? await tareasApi.desdeTarea(desde.id, datos) : await tareasApi.asignar(datos);
      window.dispatchEvent(new CustomEvent('refresh-tareas'));
      onCreada?.(t); onCerrar();
    } catch (e) { setError((e instanceof Error && e.message) || 'No se pudo crear la tarea'); }
    finally { setGuardando(false); }
  };

  return (
    <div onClick={onCerrar} style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,.35)', zIndex: 1000, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
      <div onClick={e => e.stopPropagation()} role="dialog" aria-label="Asignar tarea"
        style={{ background: '#fff', borderRadius: 8, width: 'min(560px, 96vw)', maxHeight: '92vh', overflowY: 'auto', padding: 20, boxShadow: '0 8px 32px rgba(0,0,0,.25)', fontFamily: "'Segoe UI', system-ui, sans-serif" }}>
        <h3 style={{ margin: 0, fontSize: 18 }}>Asignar tarea</h3>
        {correo && <div style={{ fontSize: 12, color: '#605e5c', marginTop: 4, display: 'flex', alignItems: 'center', gap: 4 }}><IcoClip />Enlazada al correo «{correo.subject}»</div>}
        {desde && <div style={{ fontSize: 12, color: '#605e5c', marginTop: 4 }}>La tarea pasará a tener seguimiento: estados, aceptación, recordatorios y aviso al vencer.</div>}

        <label style={lbl}>Título</label>
        <input value={titulo} onChange={e => setTitulo(e.target.value)} style={inp} autoFocus placeholder="¿Qué hay que hacer?" />

        <label style={lbl}>Asignar a</label>
        <SelectorPersonas valor={asignados} onChange={setAsignados} />

        <label style={lbl}>Plazo (fecha y hora)</label>
        <input type="datetime-local" value={plazo} onChange={e => setPlazo(e.target.value)} style={inp} />

        <label style={lbl}>Indicaciones</label>
        <textarea value={descripcion} onChange={e => setDescripcion(e.target.value)} rows={3} style={{ ...inp, resize: 'vertical' }} placeholder="Qué se espera, con qué datos, a quién entregar…" />

        {/* Lo básico arriba; lo demás, plegado (fase 2 de la unificación, 05/11/2026). */}
        <button type="button" aria-expanded={masOpciones} onClick={() => setMasOpciones(v => !v)} style={{ background: 'none', border: 'none', color: '#0078d4', cursor: 'pointer', padding: 0, marginTop: 10, fontSize: 13 }}>
          {masOpciones ? '▾' : '▸'} Más opciones (prioridad, subtareas, etiquetas, repetir, cadena, escalamiento)
        </button>
        {masOpciones && (
          <div style={{ background: '#faf9f8', borderRadius: 6, padding: '4px 12px 12px' }}>
            <label style={lbl}>Prioridad</label>
            <select value={prioridad} onChange={e => setPrioridad(e.target.value)} style={inp}>
              {Object.entries(PRIORIDAD_NOMBRE).map(([v, n]) => <option key={v} value={v}>{n}</option>)}
            </select>
            <label style={lbl}>Subtareas (una por línea)</label>
            <textarea value={subtareas} onChange={e => setSubtareas(e.target.value)} rows={2} style={{ ...inp, resize: 'vertical' }} placeholder={'Revisar cifras\nEnviar informe'} />
            <label style={lbl}>Etiquetas (separadas por coma)</label>
            <input value={etiquetas} onChange={e => setEtiquetas(e.target.value)} style={inp} placeholder="contabilidad, informe mensual" />
            <label style={lbl}>Repetir</label>
            <select value={recurrencia} onChange={e => setRecurrencia(e.target.value)} style={inp}>
              {RECURRENCIAS.map(r => <option key={r.valor} value={r.valor}>{r.nombre}</option>)}
            </select>
            <label style={lbl}>En cadena: empieza cuando se complete…</label>
            <select value={activaTareaId} onChange={e => { setActivaTareaId(e.target.value); setEnEspera(!!e.target.value); }} style={inp}>
              <option value="">— No depende de otra tarea —</option>
              {misAsignadas.map(t => <option key={t.id} value={t.id}>{t.titulo} ({t.asignados.map(a => a.split('@')[0]).join(', ')})</option>)}
            </select>
            <label style={lbl}>Jefe que recibe el escalamiento si vence (si no, el del departamento)</label>
            <SelectorPersonas valor={escalarA} onChange={setEscalarA} multiple={false} placeholder="Opcional" />
          </div>
        )}

        {error && <div style={{ color: '#a4262c', fontSize: 13, marginTop: 10 }}>{error}</div>}
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, marginTop: 16 }}>
          <button type="button" onClick={onCerrar} style={{ padding: '8px 16px', border: '1px solid #c8c6c4', background: '#fff', borderRadius: 4, cursor: 'pointer' }}>Cancelar</button>
          <button type="button" onClick={guardar} disabled={guardando} style={{ padding: '8px 18px', border: 'none', background: '#0078d4', color: '#fff', borderRadius: 4, cursor: 'pointer', fontWeight: 600 }}>
            {guardando ? 'Guardando…' : 'Asignar'}
          </button>
        </div>
      </div>
    </div>
  );
}
