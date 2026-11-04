import { useEffect, useRef } from 'react';
import { protegerEnter } from './tecladoContactos';

interface Props {
  name: string;
  permanent?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}

export function DeleteDialog({ name, permanent, onConfirm, onCancel }: Props) {
  const refCancelar = useRef<HTMLButtonElement>(null);
  const refDialogo = useRef<HTMLDivElement>(null);
  const refOnCancel = useRef(onCancel);
  useEffect(() => { refOnCancel.current = onCancel; }, [onCancel]);

  /* Al abrir, el foco va a «Cancelar» (opción segura); Escape cierra; Tab no sale del diálogo. */
  useEffect(() => {
    const previo = document.activeElement as HTMLElement | null;
    refCancelar.current?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') { e.preventDefault(); e.stopPropagation(); refOnCancel.current(); return; }
      if (e.key === 'Tab' && refDialogo.current) {
        const botones = Array.from(refDialogo.current.querySelectorAll<HTMLElement>('button'));
        if (!botones.length) return;
        const primero = botones[0], ultimo = botones[botones.length - 1];
        if (e.shiftKey && document.activeElement === primero) { e.preventDefault(); ultimo.focus(); }
        else if (!e.shiftKey && document.activeElement === ultimo) { e.preventDefault(); primero.focus(); }
      }
    };
    document.addEventListener('keydown', onKey, true);
    return () => {
      document.removeEventListener('keydown', onKey, true);
      if (previo && document.contains(previo)) previo.focus();
    };
  }, []);

  return (
    <div onKeyDown={protegerEnter} style={{
      position: 'fixed', inset: 0, zIndex: 9999,
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      backgroundColor: 'rgba(0,0,0,0.4)',
    }}>
      <div ref={refDialogo} role="dialog" aria-modal="true"
        aria-labelledby="dialogo-borrar-contacto-titulo" aria-describedby="dialogo-borrar-contacto-texto"
        style={{
        background: '#fff', borderRadius: 8, padding: 24, width: 400, maxWidth: 'calc(100vw - 32px)', boxSizing: 'border-box',
        boxShadow: '0 8px 32px rgba(0,0,0,0.25)',
        fontFamily: "'Segoe UI', Calibri, sans-serif",
      }}>
        <h3 id="dialogo-borrar-contacto-titulo" style={{ margin: 0, fontSize: 18, fontWeight: 600, color: '#323130' }}>
          {permanent ? 'Eliminar permanentemente' : 'Eliminar contacto'}
        </h3>
        <p id="dialogo-borrar-contacto-texto" style={{ fontSize: 14, color: '#605e5c', margin: '12px 0 24px' }}>
          {permanent
            ? <>¿Eliminar permanentemente a <strong>{name}</strong>? Esta acción no se puede deshacer.</>
            : <>¿Mover a <strong>{name}</strong> a la papelera? Podrás restaurarlo en los próximos 30 días.</>
          }
        </p>
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
          <button type="button" ref={refCancelar} onClick={onCancel} style={{
            padding: '8px 20px', fontSize: 13, fontWeight: 600,
            border: '1px solid #8a8886', borderRadius: 4, background: '#fff',
            color: '#323130', cursor: 'pointer',
          }}>Cancelar</button>
          <button type="button" onClick={onConfirm} style={{
            padding: '8px 20px', fontSize: 13, fontWeight: 600,
            border: 'none', borderRadius: 4, background: '#d13438',
            color: '#fff', cursor: 'pointer',
          }}>{permanent ? 'Eliminar definitivamente' : 'Eliminar'}</button>
        </div>
      </div>
    </div>
  );
}
