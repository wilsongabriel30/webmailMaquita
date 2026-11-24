/**
 * LecturaBandejaSalida.tsx — El correo de la bandeja de salida abierto en el panel de lectura (24/11/2026).
 *
 * Muestra el correo en cola como cualquier otro: asunto, destinatarios, fecha, cuerpo, y el detalle
 * útil (estado, antigüedad, intentos, último error). Desde aquí: «Editar y reenviar» (lo abre en el
 * redactor → Borradores), «Reintentar» / «Enviar ahora» y «Descartar». Un correo que el equipo ya no
 * puede leer solo deja «Descartar» y el aviso de que su borrador quedó en Borradores.
 */
import SafeEmailViewer from '../SafeEmailViewer';
import { removeFromOutbox, type OutboxEmail } from '../../../lib/offlineStore';
import { reintentarEnvio, syncOutbox, hayConexion, causaSinConexion, TEXTO_ESTADO } from '../../../lib/syncQueue';
import { esIlegible, aRedaccion, archivosDe, TEXTO_ILEGIBLE } from '../../../lib/colaSalidaLegible';
import { reabrirRedaccion } from '../../compose/reabrirRedaccion';
import { showToast } from '../../common/Toast';
import { fechaHoraLarga } from './formatoSalida';

const CAMBIO = 'outbox-cambio';

interface Props {
  item: OutboxEmail;
  onDescartado: () => void;
}

export function LecturaBandejaSalida({ item: e, onDescartado }: Props) {
  const ilegible = esIlegible(e);

  const enviarAhora = async () => {
    if (!hayConexion()) { showToast('Sin conexión: ' + causaSinConexion()); return; }
    showToast('Enviando…');
    await syncOutbox(e.id);
  };
  const reintentar = async () => {
    if (!hayConexion()) { showToast('Sin conexión: ' + causaSinConexion()); return; }
    showToast('Reintentando…');
    await reintentarEnvio(e.id);
  };
  const editar = async () => {
    reabrirRedaccion('new', aRedaccion(e), archivosDe(e));
    await removeFromOutbox(e.id);
    window.dispatchEvent(new CustomEvent(CAMBIO));
    onDescartado();
    showToast('El correo se abrió para corregirlo. Al terminar, pulse «Enviar».');
  };
  const descartar = async () => {
    if (!window.confirm(`¿Descartar «${e.subject || '(sin asunto)'}»? No se enviará y se borrará de la cola.`)) return;
    await removeFromOutbox(e.id);
    window.dispatchEvent(new CustomEvent(CAMBIO));
    onDescartado();
    showToast('Correo descartado de la bandeja de salida');
  };

  const boton = 'px-3 py-1.5 rounded border border-[#d2d0ce] bg-white text-[13px] text-[#323130] hover:bg-[#f3f2f1] dark:bg-[#2b2b2b] dark:text-[#e0e0e0] dark:border-[#444]';

  return (
    <div className="flex flex-col h-full min-h-0 bg-white dark:bg-[#1f1f1f]">
      {/* Cabecera del correo */}
      <div className="shrink-0 px-5 pt-4 pb-3 border-b border-[#edebe9] dark:border-[#3a3a3a]">
        <div className="flex items-start gap-2">
          <h1 className="text-[18px] font-semibold text-[#201f1e] dark:text-[#e0e0e0] flex-1 min-w-0 break-words">
            {e.subject || '(sin asunto)'}
          </h1>
          {e.status === 'failed' && <span className="shrink-0 mt-1 text-[11px] font-bold text-[#a4262c]">{TEXTO_ESTADO.failed}</span>}
          {e.status === 'sending' && <span className="shrink-0 mt-1 text-[11px] text-[#605e5c]">{TEXTO_ESTADO.sending}</span>}
          {(e.status === 'pending' || e.status === 'retenido') && !ilegible && <span className="shrink-0 mt-1 text-[11px] text-[#005a9e]">{TEXTO_ESTADO[e.status]}</span>}
        </div>
        <div className="mt-2 space-y-0.5 text-[13px] text-[#323130] dark:text-[#cfcfcf]">
          <div className="truncate"><span className="text-[#605e5c]">Para:</span> {(e.to || []).join(', ') || '—'}</div>
          {e.cc && e.cc.length > 0 && <div className="truncate"><span className="text-[#605e5c]">CC:</span> {e.cc.join(', ')}</div>}
          {e.bcc && e.bcc.length > 0 && <div className="truncate"><span className="text-[#605e5c]">CCO:</span> {e.bcc.join(', ')}</div>}
        </div>
        <div className="mt-1.5 text-[12px] text-[#605e5c]">
          Guardado el {fechaHoraLarga(e.createdAt)}
          {(e.retries || 0) > 0 && ` · ${e.retries} ${e.retries === 1 ? 'intento' : 'intentos'}`}
        </div>
        {ilegible ? (
          <div className="mt-2 text-[13px] text-[#a4262c]">{TEXTO_ILEGIBLE}</div>
        ) : e.status === 'failed' && e.error ? (
          <div className="mt-2 text-[13px] text-[#a4262c]">Último error: {e.error}</div>
        ) : null}

        {/* Acciones */}
        <div className="mt-3 flex flex-wrap gap-2">
          {!ilegible && e.status !== 'sending' && <button type="button" className={boton} onClick={editar}>Editar y reenviar</button>}
          {!ilegible && e.status === 'failed' && <button type="button" className={boton} onClick={reintentar}>Reintentar</button>}
          {!ilegible && (e.status === 'pending' || e.status === 'retenido') && <button type="button" className={boton} onClick={enviarAhora}>Enviar ahora</button>}
          {e.status !== 'sending' && <button type="button" className={`${boton} !text-[#a4262c]`} onClick={descartar}>Descartar</button>}
        </div>
      </div>

      {/* Cuerpo */}
      <div className="flex-1 overflow-y-auto px-5 py-4">
        {ilegible ? (
          <p className="text-[13px] text-[#605e5c]">
            El contenido de este correo se guardó cifrado y este equipo ya no puede abrirlo. No se envió.
            Su texto quedó a salvo en Borradores; envíelo desde ahí y luego descarte este.
          </p>
        ) : e.html_body && e.html_body.trim() ? (
          <SafeEmailViewer htmlBody={e.html_body} />
        ) : e.text_body && e.text_body.trim() ? (
          <pre className="whitespace-pre-wrap break-words font-sans text-[14px] text-[#201f1e] dark:text-[#e0e0e0]">{e.text_body}</pre>
        ) : (
          <p className="text-[13px] text-[#605e5c]">(Sin contenido)</p>
        )}
        {e.attachments && e.attachments.length > 0 && (
          <div className="mt-4 pt-3 border-t border-[#edebe9] dark:border-[#3a3a3a]">
            <div className="text-[12px] font-semibold text-[#605e5c] mb-1.5">
              {e.attachments.length} {e.attachments.length === 1 ? 'adjunto' : 'adjuntos'}
            </div>
            <ul className="space-y-1">
              {e.attachments.map((a, i) => (
                <li key={i} className="flex items-center gap-2 text-[13px] text-[#323130] dark:text-[#cfcfcf]">
                  <svg className="w-[14px] h-[14px] text-[#605e5c] shrink-0" fill="none" stroke="currentColor" strokeWidth={1.6} viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" d="M21.44 11.05l-9.19 9.19a5 5 0 01-7.07-7.07l9.19-9.19a3 3 0 014.24 4.24l-9.2 9.19a1 1 0 01-1.41-1.41l8.49-8.49" /></svg>
                  <span className="truncate">{a.filename || 'adjunto'}</span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </div>
  );
}
