// Panel de detalle: estado, aceptar/rechazar, subtareas (task_steps), comentarios con @menciones, correo enlazado,
// cadena, recurrencia y escalamiento. Quien asignó puede editar plazo/prioridad/asignados y eliminar.
import { useEffect, useState } from 'react';
import { tareasApi } from './api';
import { SelectorPersonas } from './SelectorPersonas';
import { Semaforo } from './TarjetaTarea';
import type { Comentario, Tarea } from './tipos';
import { ESTADO_NOMBRE, PRIORIDAD_NOMBRE, RECURRENCIAS, fechaCorta, nombreDe } from './tipos';
import { StepsList } from '../tasks/components/StepsList';

interface Props { tarea: Tarea; yo: string; onCerrar: () => void; onCambio: (t: Tarea | null) => void }
const btn: React.CSSProperties = { padding: '6px 12px', borderRadius: 4, border: '1px solid #c8c6c4', background: '#fff', cursor: 'pointer', fontSize: 13 };
const primario: React.CSSProperties = { ...btn, background: '#0078d4', color: '#fff', border: 'none', fontWeight: 600 };
const lbl: React.CSSProperties = { fontSize: 12, fontWeight: 600, color: '#605e5c', margin: '12px 0 4px', display: 'block' };
const inp: React.CSSProperties = { width: '100%', border: '1px solid #c8c6c4', borderRadius: 4, padding: '6px 8px', fontSize: 13, boxSizing: 'border-box' };

export function TareaDetalle({ tarea, yo, onCerrar, onCambio }: Props) {
  const soyAsignado = tarea.asignados.includes(yo);
  const soyAsignador = tarea.asignado_por === yo;
  const [comentarios, setComentarios] = useState<Comentario[]>([]);
  const [texto, setTexto] = useState('');
  const [motivo, setMotivo] = useState('');
  const [rechazando, setRechazando] = useState(false);
  const [editando, setEditando] = useState(false);
  const [asignados, setAsignados] = useState<string[]>(tarea.asignados);
  const [plazo, setPlazo] = useState(tarea.plazo ? new Date(tarea.plazo).toISOString().slice(0, 16) : '');
  const [prioridad, setPrioridad] = useState(tarea.prioridad);
  const [recurrencia, setRecurrencia] = useState(tarea.recurrencia || '');
  const [escalarA, setEscalarA] = useState<string[]>(tarea.escalar_a ? [tarea.escalar_a] : []);
  const [ocupado, setOcupado] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => { tareasApi.comentarios(tarea.id).then(setComentarios).catch(() => setComentarios([])); }, [tarea.id, tarea.comentarios]);
  useEffect(() => { setAsignados(tarea.asignados); setPrioridad(tarea.prioridad); setRecurrencia(tarea.recurrencia || ''); setEscalarA(tarea.escalar_a ? [tarea.escalar_a] : []); setPlazo(tarea.plazo ? new Date(new Date(tarea.plazo).getTime() - new Date().getTimezoneOffset() * 60000).toISOString().slice(0, 16) : ''); }, [tarea]);

  const ejecutar = async (fn: () => Promise<Tarea | void>) => {
    setOcupado(true); setError('');
    try { const t = await fn(); if (t) onCambio(t); window.dispatchEvent(new CustomEvent('refresh-tareas')); }
    catch (e: any) { setError(e.message || 'No se pudo'); }
    finally { setOcupado(false); }
  };
  const comentar = () => ejecutar(async () => { await tareasApi.comentar(tarea.id, texto); setTexto(''); setComentarios(await tareasApi.comentarios(tarea.id)); });
  const guardarEdicion = () => ejecutar(async () => {
    const t = await tareasApi.editar(tarea.id, { asignados, plazo: plazo ? new Date(plazo).toISOString() : null, quitar_plazo: !plazo, prioridad,
      recurrencia: recurrencia || null, quitar_recurrencia: !recurrencia, escalar_a: escalarA[0] || '' });
    setEditando(false); return t;
  });
  const eliminar = () => { if (!confirm('¿Eliminar esta tarea para todos?')) return; ejecutar(async () => { await tareasApi.eliminar(tarea.id); onCambio(null); onCerrar(); }); };
  const abrirCorreo = () => { if (tarea.correo) window.location.href = `/webmail/?folder=${encodeURIComponent(tarea.correo.folder)}&uid=${tarea.correo.uid}`; };

  return (
    <div style={{ width: 400, minWidth: 340, background: '#fff', borderLeft: '1px solid #edebe9', height: '100%', overflowY: 'auto', padding: 16, fontFamily: "'Segoe UI', system-ui, sans-serif", boxSizing: 'border-box' }}>
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 8 }}>
        <h3 style={{ margin: 0, fontSize: 17, flex: 1, textDecoration: tarea.estado === 'completada' ? 'line-through' : 'none' }}>{tarea.titulo}</h3>
        <button onClick={onCerrar} aria-label="Cerrar" style={{ ...btn, border: 'none', fontSize: 18, lineHeight: 1 }}>×</button>
      </div>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10, fontSize: 12, color: '#605e5c', marginTop: 8 }}>
        <Semaforo tarea={tarea} /><span>📅 {fechaCorta(tarea.plazo)}</span><span>{PRIORIDAD_NOMBRE[tarea.prioridad]}</span>
        <span style={{ background: '#f3f2f1', borderRadius: 10, padding: '1px 7px' }}>{ESTADO_NOMBRE[tarea.estado]}</span>
        {tarea.recurrencia && <span>🔁 {RECURRENCIAS.find(r => r.valor === tarea.recurrencia)?.nombre}</span>}
      </div>
      <div style={{ fontSize: 13, marginTop: 8 }}><b>Asignada a:</b> {tarea.asignados.map(nombreDe).join(', ')} · <b>por:</b> {nombreDe(tarea.asignado_por)}</div>
      {tarea.aceptacion === 'aceptada' && <div style={{ fontSize: 12, color: '#107c10', marginTop: 4 }}>✔ Aceptada por el asignado</div>}
      {tarea.aceptacion === 'rechazada' && <div style={{ fontSize: 12, color: '#a4262c', marginTop: 4 }}>✖ Rechazada: {tarea.motivo_rechazo || 'sin motivo'}</div>}
      {tarea.escalado_en && <div style={{ fontSize: 12, color: '#a4262c', marginTop: 4 }}>⬆ Escalada al jefe el {fechaCorta(tarea.escalado_en)}</div>}
      {tarea.estado === 'espera' && <div style={{ fontSize: 12, color: '#605e5c', marginTop: 4 }}>⏳ En espera: empieza cuando se complete la tarea anterior de la cadena.</div>}
      {tarea.activa_tarea_id && <div style={{ fontSize: 12, color: '#605e5c', marginTop: 4 }}>⛓ Al completarse activa la siguiente tarea de la cadena.</div>}
      {tarea.descripcion && <div style={{ fontSize: 13, marginTop: 10, whiteSpace: 'pre-wrap', color: '#323130' }} dangerouslySetInnerHTML={{ __html: tarea.descripcion }} />}
      {tarea.correo && <button onClick={abrirCorreo} style={{ ...btn, marginTop: 8 }}>📎 Abrir el correo «{tarea.correo.subject || 'sin asunto'}»</button>}

      {/* Acciones */}
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginTop: 14 }}>
        {soyAsignado && tarea.aceptacion !== 'aceptada' && tarea.estado !== 'completada' && tarea.estado !== 'espera' && <>
          <button disabled={ocupado} style={primario} onClick={() => ejecutar(() => tareasApi.aceptar(tarea.id))}>Aceptar tarea</button>
          <button disabled={ocupado} style={btn} onClick={() => setRechazando(v => !v)}>Rechazar…</button>
        </>}
        {tarea.estado !== 'completada' && tarea.estado !== 'espera' && (soyAsignado || soyAsignador) && <>
          {tarea.estado !== 'en_curso' && <button disabled={ocupado} style={btn} onClick={() => ejecutar(() => tareasApi.estado(tarea.id, 'en_curso'))}>▶ En curso</button>}
          <button disabled={ocupado} style={{ ...primario, background: '#107c10' }} onClick={() => ejecutar(() => tareasApi.completar(tarea.id))}>✔ Completar</button>
        </>}
        {tarea.estado === 'completada' && (soyAsignado || soyAsignador) && <button disabled={ocupado} style={btn} onClick={() => ejecutar(() => tareasApi.estado(tarea.id, 'pendiente'))}>Reabrir</button>}
        {soyAsignador && <button style={btn} onClick={() => setEditando(v => !v)}>✎ Editar</button>}
        {soyAsignador && <button style={{ ...btn, color: '#a4262c' }} onClick={eliminar}>Eliminar</button>}
      </div>
      {rechazando && (
        <div style={{ marginTop: 8 }}>
          <input value={motivo} onChange={e => setMotivo(e.target.value)} placeholder="Motivo del rechazo" style={inp} />
          <button disabled={ocupado} style={{ ...btn, marginTop: 6, color: '#a4262c' }} onClick={() => ejecutar(async () => { const t = await tareasApi.rechazar(tarea.id, motivo); setRechazando(false); return t; })}>Confirmar rechazo</button>
        </div>
      )}
      {editando && (
        <div style={{ background: '#faf9f8', borderRadius: 6, padding: '4px 12px 12px', marginTop: 10 }}>
          <label style={lbl}>Asignar a</label><SelectorPersonas valor={asignados} onChange={setAsignados} />
          <label style={lbl}>Plazo</label><input type="datetime-local" value={plazo} onChange={e => setPlazo(e.target.value)} style={inp} />
          <label style={lbl}>Prioridad</label>
          <select value={prioridad} onChange={e => setPrioridad(e.target.value as Tarea['prioridad'])} style={inp}>{Object.entries(PRIORIDAD_NOMBRE).map(([v, n]) => <option key={v} value={v}>{n}</option>)}</select>
          <label style={lbl}>Repetir</label>
          <select value={recurrencia} onChange={e => setRecurrencia(e.target.value)} style={inp}>{RECURRENCIAS.map(r => <option key={r.valor} value={r.valor}>{r.nombre}</option>)}</select>
          <label style={lbl}>Jefe para escalamiento</label><SelectorPersonas valor={escalarA} onChange={setEscalarA} multiple={false} placeholder="Opcional" />
          <button disabled={ocupado} style={{ ...primario, marginTop: 10 }} onClick={guardarEdicion}>Guardar cambios</button>
        </div>
      )}
      {error && <div style={{ color: '#a4262c', fontSize: 13, marginTop: 8 }}>{error}</div>}

      <label style={lbl}>Subtareas</label>
      <StepsList cardId={tarea.id} />

      <label style={lbl}>Comentarios ({comentarios.length})</label>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {comentarios.map(c => (
          <div key={c.id} style={{ background: '#f3f2f1', borderRadius: 6, padding: '6px 10px', fontSize: 13 }}>
            <div style={{ fontSize: 11, color: '#605e5c' }}><b>{nombreDe(c.autor)}</b> · {fechaCorta(c.creado_en)}</div>
            <div style={{ whiteSpace: 'pre-wrap' }}>{c.texto}</div>
          </div>
        ))}
      </div>
      <textarea value={texto} onChange={e => setTexto(e.target.value)} rows={2} placeholder="Escribe un comentario. Menciona con @correo para avisar a alguien." style={{ ...inp, marginTop: 8, resize: 'vertical' }}
        onKeyDown={e => { if (e.key === 'Enter' && (e.ctrlKey || e.metaKey) && texto.trim()) comentar(); }} />
      <button disabled={ocupado || !texto.trim()} style={{ ...primario, marginTop: 6 }} onClick={comentar}>Comentar</button>
    </div>
  );
}
