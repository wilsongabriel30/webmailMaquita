import { PuntoLeido } from './PuntoLeido';
import { memo } from 'react';
import type { MessageSummary } from '../../types';
import { AvatarFoto } from '../common/AvatarFoto';

/**
 * Fila de correo en UNA sola línea (densidad «Una línea», 05/11/2026).
 *
 * Reproduce la lista de Outlook sin panel de lectura: De | Asunto + vista previa | Fecha.
 * Ocupa ~32 px por correo frente a los ~66 px de la fila de tres líneas, así que en los
 * equipos con pantalla pequeña (la mayoría) caben el doble de correos sin desplazarse.
 * Solo presenta; la lógica (clic, arrastre, menú contextual, acciones) viene por props
 * desde MessageList para no duplicarla.
 */

export interface FilaCorreoLineaProps {
  /** true = el asunto va antes que el nombre (06/11/2026) */
  asuntoPrimero?: boolean;
  msg: MessageSummary;
  idx: number;
  nombre: string;
  iniciales: string;
  /** Foto del directorio (Raíces o propia); si falta o falla, se ven las iniciales (09/11/2026). */
  fotoUrl?: string;
  color: string;
  fecha: string;
  activo: boolean;
  marcado: boolean;          // seleccionado con casilla
  fijado: boolean;
  esSpam: boolean;
  motivoSpam?: string;
  threadCount?: number;
  etiquetas: { id: string | number; name: string; color?: string }[];
  onClick: (e: React.MouseEvent) => void;
  onDoubleClick: () => void;
  onContextMenu: (e: React.MouseEvent) => void;
  onDragStart: (e: React.DragEvent) => void;
  onMarcar: (e: React.MouseEvent) => void;      // casilla / avatar
  onBandera: (e: React.MouseEvent) => void;
  onEliminar: (e: React.MouseEvent) => void;
  onArchivar: (e: React.MouseEvent) => void;
  onLeido: (e: React.MouseEvent) => void;
  /** Chincheta: anclar arriba de la lista (07/11/2026). */
  onFijar?: (e: React.MouseEvent) => void;
}

const flagIcon = 'M3 21v-4m0 0V5a2 2 0 012-2h6.5l1 1H21l-3 6 3 6h-8.5l-1-1H5a2 2 0 00-2 2z';
const deleteIcon = 'M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16';
const pinIcon = 'M14.5 3.5l6 6-2.6.9-3.7 3.7.4 4.1-1.6 1.6-3.6-3.6L4.5 21l-1.5-1.5 4.8-4.9-3.6-3.6 1.6-1.6 4.1.4 3.7-3.7z';
const archiveIcon = 'M5 8h14M5 8a2 2 0 110-4h14a2 2 0 110 4M5 8v10a2 2 0 002 2h10a2 2 0 002-2V8m-9 4h4';
const unreadIcon = 'M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z';

function Icono({ d, filled, className }: { d: string; filled?: boolean; className?: string }) {
  return (
    <svg className={className || 'w-[14px] h-[14px]'} fill={filled ? 'currentColor' : 'none'} stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d={d} />
    </svg>
  );
}

function Rapida({ d, title, onClick, filled }: { d: string; title: string; onClick: (e: React.MouseEvent) => void; filled?: boolean }) {
  return (
    <button onClick={onClick} title={title}
      className="w-[24px] h-[24px] rounded flex items-center justify-center text-[#605e5c] hover:bg-[#e1dfdd] hover:text-[#323130] transition-colors">
      <Icono d={d} filled={filled} className="w-[13px] h-[13px]" />
    </button>
  );
}

export const FilaCorreoLinea = memo(function FilaCorreoLinea(p: FilaCorreoLineaProps) {
  const { msg } = p;
  const noLeido = !msg.seen;
  const bloqueDe = (
    <div className="flex items-center gap-1 w-[150px] lg:w-[190px] xl:w-[220px] shrink-0 min-w-0">
      <span className={`text-[13px] truncate ${noLeido ? 'font-semibold text-[#323130]' : 'text-[#323130]'}`}>{p.nombre}</span>
      {p.threadCount && p.threadCount > 1 ? (
        <span className="inline-flex items-center justify-center min-w-[16px] h-[16px] px-1 rounded-full bg-[#0078d4] text-white text-[10px] font-semibold shrink-0">{p.threadCount}</span>
      ) : null}
    </div>
  );
  const bloqueAsunto = (
    <div className="flex-1 min-w-0 flex items-center gap-1.5">
      {/* El asunto conserva al menos la mitad del espacio: la vista previa no lo puede desplazar (06/11/2026) */}
      <span className={`text-[13px] truncate min-w-[50%] ${noLeido ? 'font-semibold text-[#0078d4]' : 'text-[#323130]'}`}>
        {msg.subject || '(Sin asunto)'}
      </span>
      {p.etiquetas.map((lbl) => (
        <span key={lbl.id} title={lbl.name}
          className="shrink-0 inline-flex items-center px-1.5 h-[15px] rounded-[3px] text-[10px] font-medium text-white capitalize leading-none"
          style={{ backgroundColor: lbl.color }}>
          {String(lbl.name).replace(/^Categor[ií]a\s+/i, '') || lbl.name}
        </span>
      ))}
      {msg.snippet ? (
        <span className="text-[12px] text-[#605e5c] truncate min-w-0 flex-1">{msg.snippet}</span>
      ) : null}
    </div>
  );
  return (
    <div
      draggable
      onDragStart={p.onDragStart}
      onClick={p.onClick}
      onDoubleClick={p.onDoubleClick}
      data-idx={p.idx}
      onContextMenu={p.onContextMenu}
      className={`group relative flex items-center gap-2 pl-1.5 pr-2 h-[32px] cursor-pointer border-b border-[#f3f2f1] ${
        p.marcado ? 'bg-[#deecf9]' : p.activo ? 'bg-[#eff6fc]' : 'hover:bg-[#f3f2f1]'
      } ${noLeido ? "before:content-[''] before:absolute before:left-0 before:top-0 before:-bottom-px before:w-[3px] before:bg-[#0078d4] before:z-[1]" : ''}`}
    >
      {/* Punto de no leído / aviso de spam */}
      <div className="w-[4px] shrink-0 flex items-center">
        <PuntoLeido noLeido={noLeido} esSpam={p.esSpam} motivoSpam={p.motivoSpam} onAlternar={p.onLeido} />
      </div>

      {/* Casilla pequeña: avatar con iniciales que al pasar el ratón se vuelve casilla */}
      <div className="shrink-0" title={p.marcado ? 'Quitar de la selección' : 'Seleccionar'}
          onClick={p.onMarcar}>
          {/* Como Outlook (07/11/2026): al pasar el ratón el círculo se cambia por una casilla cuadrada blanca;
              marcado = casilla azul con visto. Varias marcadas → la cinta actúa sobre todas o se arrastran juntas. */}
          <div className={`w-[20px] h-[20px] rounded-full flex items-center justify-center text-[9px] font-semibold text-white cursor-pointer ${
            p.marcado ? '' : 'group-hover:!bg-transparent'
          }`} style={p.marcado ? {} : { backgroundColor: p.color }}>
            {p.marcado ? (
              <span className="w-[16px] h-[16px] rounded-[3px] bg-[#0078d4] flex items-center justify-center">
                <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 20 20"><path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" /></svg>
              </span>
            ) : (<>
              <span className="group-hover:hidden flex">
                <AvatarFoto url={p.fotoUrl} initials={p.iniciales} size={20} color={p.color} fontSize={9} />
              </span>
              <span className="hidden group-hover:block w-[16px] h-[16px] rounded-[3px] bg-white border-[1.5px] border-[#605e5c] hover:border-[#0078d4]" />
            </>)}
          </div>
      </div>

      {/* Orden elegido por la persona (06/11/2026): asunto primero (lo habitual) o nombre primero (como Outlook) */}
      {p.asuntoPrimero ? <>{bloqueAsunto}{bloqueDe}</> : <>{bloqueDe}{bloqueAsunto}</>}

      {/* Indicadores */}
      <div className="flex items-center gap-1 shrink-0">
        {p.fijado && (
          <svg className="w-[12px] h-[12px] text-[#0078d4]" fill="currentColor" viewBox="0 0 20 20"><title>Fijado</title>
            <path d="M9 2a1 1 0 00-1 1v4.586L5.707 9.879A1 1 0 006.414 11.5H9V17a1 1 0 002 0v-5.5h2.586a1 1 0 00.707-1.621L12 7.586V3a1 1 0 00-1-1H9z" /></svg>
        )}
        {msg.has_attachments && (
          <svg className="w-[12px] h-[12px] text-[#605e5c]" fill="none" stroke="currentColor" viewBox="0 0 24 24"><title>Con adjunto</title>
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.172 7l-6.586 6.586a2 2 0 102.828 2.828l6.414-6.586a4 4 0 00-5.656-5.656l-6.415 6.585a6 6 0 108.486 8.486L20.5 13" /></svg>
        )}
        {msg.importance === 'high' && (
          <svg className="w-[12px] h-[12px] text-[#d13438]" fill="currentColor" viewBox="0 0 20 20"><title>Importante</title>
            <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" /></svg>
        )}
      </div>

      {/* Fecha: se oculta al pasar el ratón para dejar sitio a las acciones rápidas */}
      <span className={`text-[12px] w-[72px] text-right shrink-0 group-hover:invisible ${noLeido ? 'font-semibold text-[#0078d4]' : 'text-[#605e5c]'}`}>{p.fecha}</span>

      {/* Bandera */}
      <button onClick={p.onBandera} title={msg.flagged ? 'Quitar marca' : 'Marcar'}
        className={`shrink-0 transition-colors ${msg.flagged ? 'text-[#d13438]' : 'text-transparent group-hover:text-[#a19f9d] hover:!text-[#d13438]'}`}>
        <Icono d={flagIcon} filled={!!msg.flagged} className="w-[13px] h-[13px]" />
      </button>

      {/* Acciones rápidas (escritorio) */}
      <div className="hidden group-hover:flex max-md:hidden items-center gap-0.5 absolute right-7 top-[3px] bg-[#f3f2f1] rounded shadow-sm border border-[#e1dfdd] px-0.5">
        <Rapida d={unreadIcon} title={msg.seen ? 'Marcar como no leído' : 'Marcar como leído'} onClick={p.onLeido} />
        {p.onFijar && <Rapida d={pinIcon} title={p.fijado ? 'Desanclar' : 'Anclar arriba'} filled={p.fijado} onClick={p.onFijar} />}
        <Rapida d={archiveIcon} title="Archivar" onClick={p.onArchivar} />
        <Rapida d={deleteIcon} title="Eliminar" onClick={p.onEliminar} />
      </div>
    </div>
  );
});
