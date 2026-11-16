// Ventana de confirmación de la aplicación. Se pide con `confirmar()` (lib/confirmar.ts) y se
// dibuja aquí; está montada junto a los avisos flotantes (ToastContainer).
import { useEffect, useRef, useState } from 'react';
import { suscribirConfirmaciones, type PeticionConfirmar } from '../../lib/confirmar';

interface Pendiente { peticion: PeticionConfirmar; responder: (acepta: boolean) => void }

export function DialogoConfirmar() {
  const [pendiente, setPendiente] = useState<Pendiente | null>(null);
  const refPendiente = useRef<Pendiente | null>(null);
  const refDialogo = useRef<HTMLDivElement>(null);
  const refCancelar = useRef<HTMLButtonElement>(null);

  const cerrar = (acepta: boolean) => {
    const p = refPendiente.current;
    refPendiente.current = null;
    setPendiente(null);
    p?.responder(acepta);
  };

  useEffect(() => suscribirConfirmaciones((peticion, responder) => {
    refPendiente.current?.responder(false);   // una pregunta nueva cancela la anterior
    refPendiente.current = { peticion, responder };
    setPendiente(refPendiente.current);
  }), []);
  // Si la pantalla se desmonta con una pregunta abierta, se responde «no».
  useEffect(() => () => { refPendiente.current?.responder(false); refPendiente.current = null; }, []);

  /* Al abrir, el foco va a «Cancelar» (opción segura); Escape cancela; Tab no sale del diálogo. */
  useEffect(() => {
    if (!pendiente) return;
    const previo = document.activeElement as HTMLElement | null;
    refCancelar.current?.focus();
    const alTeclear = (e: KeyboardEvent) => {
      if (e.key === 'Escape') { e.preventDefault(); e.stopPropagation(); cerrar(false); return; }
      if (e.key === 'Tab' && refDialogo.current) {
        const botones = Array.from(refDialogo.current.querySelectorAll<HTMLElement>('button'));
        if (!botones.length) return;
        const primero = botones[0], ultimo = botones[botones.length - 1];
        if (e.shiftKey && document.activeElement === primero) { e.preventDefault(); ultimo.focus(); }
        else if (!e.shiftKey && document.activeElement === ultimo) { e.preventDefault(); primero.focus(); }
      }
    };
    document.addEventListener('keydown', alTeclear, true);
    return () => {
      document.removeEventListener('keydown', alTeclear, true);
      if (previo && document.contains(previo)) previo.focus();
    };
  }, [pendiente]);

  if (!pendiente) return null;
  const { titulo, texto, aceptar, peligro } = pendiente.peticion;
  const parrafos = Array.isArray(texto) ? texto : [texto];

  return (
    <div className="fixed inset-0 z-[10000] flex items-center justify-center bg-black/40 dark:bg-black/60 px-4"
      onClick={() => cerrar(false)}>
      <div ref={refDialogo} role="alertdialog" aria-modal="true"
        aria-labelledby="dialogo-confirmar-titulo" aria-describedby="dialogo-confirmar-texto"
        onClick={(e) => e.stopPropagation()}
        className="w-full max-w-[440px] rounded-lg bg-white dark:bg-[#2d2d2d] border border-[#edebe9] dark:border-[#444] shadow-xl p-6">
        <h3 id="dialogo-confirmar-titulo" className="m-0 text-[18px] font-semibold text-[#323130] dark:text-[#e0e0e0]">{titulo}</h3>
        <div id="dialogo-confirmar-texto" className="mt-3 mb-6 space-y-2 text-[14px] text-[#605e5c] dark:text-[#c8c6c4]">
          {parrafos.map((p, i) => <p key={i} className="m-0 break-words">{p}</p>)}
        </div>
        <div className="flex justify-end gap-2">
          <button type="button" ref={refCancelar} onClick={() => cerrar(false)}
            className="px-5 py-2 text-[13px] font-semibold rounded border border-[#8a8886] bg-white text-[#323130] hover:bg-[#f3f2f1] dark:bg-[#2d2d2d] dark:text-[#e0e0e0] dark:hover:bg-[#383838]">
            Cancelar
          </button>
          <button type="button" onClick={() => cerrar(true)}
            className={`px-5 py-2 text-[13px] font-semibold rounded text-white ${peligro ? 'bg-[#d13438] hover:bg-[#a4262c]' : 'bg-[#0078d4] hover:bg-[#106ebe]'}`}>
            {aceptar || 'Aceptar'}
          </button>
        </div>
      </div>
    </div>
  );
}
