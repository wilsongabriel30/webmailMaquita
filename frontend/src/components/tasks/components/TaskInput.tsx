// Barra para agregar una tarea, como en Outlook (F6): «○ Agregar una tarea» y, debajo, fecha de vencimiento,
// recordatorio y repetición, con «Agregar» a la derecha. Enter también agrega.
import { useRef, useState } from 'react';
import { COLORS, type ActiveView } from '../types';
import { REPETICIONES_SIMPLES, etiquetaRepeticion } from './repeticion';
import { SelectorRapido } from './SelectorRapido';

interface Props {
  onAdd: (title: string, dueDate?: string, reminder?: string, recurrence?: string) => void;
  activeView: ActiveView;
}

function dia(n: number): string {
  const d = new Date();
  d.setDate(d.getDate() + n);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}
const lunes = () => { const g = new Date().getDay(); return g === 0 ? 1 : 8 - g; };
const a9 = (n: number) => { const d = new Date(); d.setDate(d.getDate() + n); d.setHours(9, 0, 0, 0); return d.toISOString(); };

const FECHAS = [
  { etiqueta: 'Hoy', valor: () => dia(0) },
  { etiqueta: 'Mañana', valor: () => dia(1) },
  { etiqueta: 'La próxima semana', valor: () => dia(lunes()) },
];
const RECORDATORIOS = [
  { etiqueta: 'Más tarde hoy', valor: () => new Date(Date.now() + 3 * 3600000).toISOString() },
  { etiqueta: 'Mañana (9:00)', valor: () => a9(1) },
  { etiqueta: 'La próxima semana (lunes 9:00)', valor: () => a9(lunes()) },
];
const REPETIR = REPETICIONES_SIMPLES.map(r => ({ etiqueta: r.etiqueta, valor: () => r.valor }));

const icono = (d: string) => (
  <svg aria-hidden="true" width={18} height={18} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round"><path d={d} /></svg>
);
const CALENDARIO = 'M5 4h14a2 2 0 012 2v13a2 2 0 01-2 2H5a2 2 0 01-2-2V6a2 2 0 012-2zM3 9h18M8 13h.01M12 13h.01M16 13h.01M8 17h.01M12 17h.01';
const CAMPANA = 'M18 8A6 6 0 006 8c0 7-3 9-3 9h18s-3-2-3-9M13.73 21a2 2 0 01-3.46 0';
const REPETICION = 'M17 2l4 4-4 4M3 11V9a3 3 0 013-3h15M7 22l-4-4 4-4M21 13v2a3 3 0 01-3 3H3';

function Ficha({ texto, onQuitar }: { texto: string; onQuitar: () => void }) {
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, fontSize: 12, color: COLORS.primary }}>
      {texto}
      <button type="button" aria-label={`Quitar ${texto}`} onClick={onQuitar}
        style={{ background: 'none', border: 'none', cursor: 'pointer', color: COLORS.secondary, fontSize: 14, padding: 0, lineHeight: 1 }}>&times;</button>
    </span>
  );
}

export function TaskInput({ onAdd, activeView }: Props) {
  const [title, setTitle] = useState('');
  const [dueDate, setDueDate] = useState('');
  const [reminder, setReminder] = useState('');
  const [recurrence, setRecurrence] = useState('');
  const [aviso, setAviso] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  // Al cambiar de vista se descarta lo elegido para la tarea a medio escribir.
  const [vistaAnterior, setVistaAnterior] = useState(activeView);
  if (vistaAnterior !== activeView) {
    setVistaAnterior(activeView);
    setDueDate(''); setReminder(''); setRecurrence('');
  }

  const handleAdd = () => {
    if (!title.trim()) {
      inputRef.current?.focus();
      setAviso(true);
      window.setTimeout(() => setAviso(false), 1500);
      return;
    }
    // Como en To Do: una tarea que se repite y no tiene fecha vence hoy.
    onAdd(title.trim(), dueDate || (recurrence ? dia(0) : undefined), reminder || undefined, recurrence || undefined);
    setTitle(''); setDueDate(''); setReminder(''); setRecurrence('');
  };

  const fechaTexto = dueDate === dia(0) ? 'Hoy' : dueDate === dia(1) ? 'Mañana'
    : dueDate ? new Date(dueDate + 'T12:00:00').toLocaleDateString('es-ES', { weekday: 'short', day: 'numeric', month: 'short' }) : '';
  const recordatorioTexto = reminder
    ? new Date(reminder).toLocaleString('es-ES', { weekday: 'short', day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' }) : '';

  return (
    <div className="barra-agregar" style={{
      margin: '0 24px', background: 'white', borderRadius: 4, boxShadow: '0 1px 2px rgba(0,0,0,0.1)',
      fontFamily: "'Segoe UI', system-ui, sans-serif",
    }}>
      <style>{`.barra-agregar input.nueva-tarea::placeholder { color: ${COLORS.primary}; }`}</style>
      <div style={{ display: 'flex', alignItems: 'center', gap: 14, padding: '0 16px', height: 52 }}>
        <span aria-hidden="true" style={{ width: 18, height: 18, borderRadius: '50%', border: `1.5px solid ${COLORS.primary}`, flexShrink: 0 }} />
        <input ref={inputRef} className="nueva-tarea" value={title} autoFocus aria-label="Agregar una tarea"
          onChange={e => setTitle(e.target.value)} onKeyDown={e => { if (e.key === 'Enter') handleAdd(); }}
          placeholder="Agregar una tarea"
          style={{ flex: 1, border: 'none', outline: 'none', fontSize: 15, color: COLORS.text, background: 'transparent', fontFamily: 'inherit' }} />
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '6px 12px', borderTop: `1px solid ${COLORS.border}`, background: '#faf9f8', flexWrap: 'wrap' }}>
        <SelectorRapido titulo="Fecha de vencimiento" icono={icono(CALENDARIO)} activo={!!dueDate} opciones={FECHAS} campo="date" onElegir={setDueDate} />
        <SelectorRapido titulo="Recordarme" icono={icono(CAMPANA)} activo={!!reminder} opciones={RECORDATORIOS} campo="datetime-local" onElegir={setReminder} />
        <SelectorRapido titulo="Repetir" icono={icono(REPETICION)} activo={!!recurrence} opciones={REPETIR} onElegir={setRecurrence} />
        {dueDate && <Ficha texto={fechaTexto} onQuitar={() => setDueDate('')} />}
        {reminder && <Ficha texto={recordatorioTexto} onQuitar={() => setReminder('')} />}
        {recurrence && <Ficha texto={etiquetaRepeticion(recurrence)} onQuitar={() => setRecurrence('')} />}
        <span style={{ flex: 1 }} />
        {aviso && <span role="status" style={{ fontSize: 12, color: '#d13438' }}>Escribe el título de la tarea</span>}
        <button type="button" onClick={handleAdd} disabled={!title.trim()}
          style={{
            padding: '5px 14px', fontSize: 13, borderRadius: 4, fontFamily: 'inherit',
            border: `1px solid ${title.trim() ? COLORS.primary : COLORS.border}`,
            background: title.trim() ? COLORS.primary : 'white', color: title.trim() ? 'white' : COLORS.muted,
            cursor: title.trim() ? 'pointer' : 'default',
          }}>
          Agregar
        </button>
      </div>
    </div>
  );
}
