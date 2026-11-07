/**
 * Vista previa del asistente de redacción, dentro de la caja donde se escribe el correo.
 *
 * La propuesta se va mostrando mientras la IA la genera, arriba del texto original (que sigue a la
 * vista debajo para comparar). Nada cambia hasta pulsar «Aplicar»; Ctrl+Z la deshace. Mientras la
 * vista previa está abierta el editor queda en solo lectura, para que la propuesta corresponda al
 * texto que se envió.
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import type { Editor } from '@tiptap/react';
import { showToast } from '../../common/Toast';
import { IndicadorGenerando } from '../../ai/IndicadorGenerando';
import { EVENTO_REDACCION_IA, MODOS, type ModoRedaccion } from './modos';
import { aplicarPropuesta, limpiarHtml, tomarAlcance, type Alcance } from './alcance';
import { pedirRedaccion } from './pedirRedaccion';

type Estado = 'generando' | 'lista' | 'error';

const ESTILO_TEXTO = '[&_ul]:list-disc [&_ul]:pl-6 [&_ol]:list-decimal [&_ol]:pl-6 [&_p]:mb-1 [&_li]:mb-[2px]';

export function VistaPreviaRedaccion({ editor, asunto, activo }: { editor: Editor | null; asunto: string; activo: boolean }) {
  const [abierta, setAbierta] = useState(false);
  const [modo, setModo] = useState<ModoRedaccion>('ortografia');
  const [estado, setEstado] = useState<Estado>('generando');
  const [html, setHtml] = useState('');
  const [error, setError] = useState('');
  const [fragmento, setFragmento] = useState(false);
  const [intento, setIntento] = useState(0); // reinicia la cuenta regresiva en cada pedido
  const alcance = useRef<Alcance | null>(null);
  const control = useRef<AbortController | null>(null);

  const generar = useCallback((m: ModoRedaccion) => {
    const a = alcance.current;
    if (!a) return;
    control.current?.abort();
    const c = new AbortController();
    control.current = c;
    setModo(m); setEstado('generando'); setHtml(''); setError(''); setIntento((n) => n + 1);
    pedirRedaccion({ text: a.texto, modo: m, fragmento: a.fragmento, asunto: asunto || undefined }, {
      alAvanzar: (h) => { if (!c.signal.aborted) setHtml(h); },
      alTerminar: (h) => { if (!c.signal.aborted) { setHtml(h); setEstado('lista'); } },
      alFallar: (msg) => { if (!c.signal.aborted) { setError(msg); setEstado('error'); } },
    }, c.signal);
  }, [asunto]);

  const cerrar = useCallback(() => {
    control.current?.abort();
    control.current = null;
    alcance.current = null;
    setAbierta(false);
    if (editor && !editor.isDestroyed) editor.setEditable(true);
  }, [editor]);

  const abrir = useCallback((m: ModoRedaccion) => {
    if (!editor || editor.isDestroyed) return;
    const a = tomarAlcance(editor);
    if (typeof a === 'string') { showToast(a); return; }
    alcance.current = a;
    setFragmento(a.fragmento);
    editor.setEditable(false);
    setAbierta(true);
    generar(m);
  }, [editor, generar]);

  useEffect(() => {
    if (!activo) return;
    const conModo = (e: Event) => abrir((e as CustomEvent<{ modo?: ModoRedaccion }>).detail?.modo || 'ortografia');
    const mejorar = () => abrir('redaccion');
    window.addEventListener(EVENTO_REDACCION_IA, conModo);
    window.addEventListener('compose-improve-writing', mejorar);
    return () => {
      window.removeEventListener(EVENTO_REDACCION_IA, conModo);
      window.removeEventListener('compose-improve-writing', mejorar);
    };
  }, [activo, abrir]);

  useEffect(() => {
    if (!abierta) return;
    const tecla = (e: KeyboardEvent) => { if (e.key === 'Escape') { e.stopPropagation(); cerrar(); } };
    window.addEventListener('keydown', tecla, true);
    return () => window.removeEventListener('keydown', tecla, true);
  }, [abierta, cerrar]);

  // Al cerrar la ventana de redacción con la vista previa abierta
  useEffect(() => () => control.current?.abort(), []);

  if (!abierta) return null;

  const aplicar = () => {
    if (!editor || !alcance.current || estado !== 'lista') return;
    const a = alcance.current;
    cerrar();
    aplicarPropuesta(editor, a, html);
    showToast('Propuesta aplicada. Ctrl+Z la deshace.');
  };

  return (
    <div role="dialog" aria-label="Vista previa del asistente de redacción"
      className="sticky top-0 z-20 mx-4 mt-2 mb-3 bg-white border border-[#c7e0f4] rounded-md shadow-md flex flex-col max-h-[65%]">
      <div className="flex items-center gap-2 px-3 py-2 bg-[#f0f6ff] border-b border-[#c7e0f4] rounded-t-md">
        <svg width={14} height={14} viewBox="0 0 24 24" fill="none" stroke="#0078d4" strokeWidth={1.5} className="shrink-0">
          <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09z" />
        </svg>
        <span className="text-[12px] font-semibold text-[#323130]">Propuesta de la IA</span>
        <span className="text-[11px] text-[#605e5c] truncate">
          · {fragmento ?'texto seleccionado' : 'todo el mensaje (sin la firma ni el texto citado)'}
        </span>
        <button onClick={cerrar} title="Cerrar sin cambiar nada (Esc)" aria-label="Cerrar"
          className="ml-auto text-[13px] text-[#605e5c] hover:text-[#323130] px-1">{'✕'}</button>
      </div>

      <div className="flex flex-wrap gap-1 px-3 pt-2">
        {MODOS.map((m) => (
          <button key={m.id} onClick={() => generar(m.id)} title={m.detalle} aria-pressed={modo === m.id}
            className={`text-[11px] px-2 py-[3px] rounded-full border transition-colors ${
              modo === m.id ? 'bg-[#0078d4] border-[#0078d4] text-white' : 'border-[#c8c6c4] text-[#323130] hover:bg-[#f3f2f1]'
            }`}>
            {m.etiqueta}
          </button>
        ))}
      </div>

      <div className="flex-1 overflow-y-auto text-[14px] leading-[1.5] text-[#323130] min-h-[60px]" aria-live="polite">
        {estado === 'error' ? (
          <p className="px-4 py-3 text-[13px] text-[#a4262c]">{error}</p>
        ) : html ? (
          <div className={`px-4 py-3 ${ESTILO_TEXTO}`} dangerouslySetInnerHTML={{ __html: limpiarHtml(html) }} />
        ) : (
          // Misma cuenta regresiva que «Responder con IA» mientras no llega la primera frase (05/11/2026).
          <IndicadorGenerando key={intento} funcion="redaccion" onCancelar={cerrar} />
        )}
      </div>

      <div className="flex items-center gap-2 px-3 py-2 border-t border-[#edebe9]">
        <button onClick={aplicar} disabled={estado !== 'lista'}
          className="text-[12px] font-semibold text-white bg-[#0078d4] hover:bg-[#106ebe] disabled:opacity-50 px-3 py-1 rounded">
          Aplicar
        </button>
        <button onClick={() => generar(modo)} disabled={estado === 'generando'}
          className="text-[12px] text-[#0078d4] hover:bg-[#deecf9] disabled:opacity-50 px-2 py-1 rounded">
          Otra versión
        </button>
        <button onClick={cerrar} className="text-[12px] text-[#605e5c] hover:bg-[#f3f2f1] px-2 py-1 rounded">Descartar</button>
        <span className="ml-auto text-[11px] text-[#605e5c]">
          {estado === 'generando' ? 'Escribiendo la propuesta…' : estado === 'lista' ? 'Revise antes de aplicar: la IA puede equivocarse.' : ''}
        </span>
      </div>
    </div>
  );
}
