/**
 * ListResizeHandle.tsx — Divisor arrastrable entre la lista de mensajes y el panel de lectura.
 *
 * Al arrastrarlo cambia el ancho de la lista (`messageListWidth` del store, recordado entre cargas);
 * el panel de la derecha (flex-1) se ajusta solo. Lo usan la vista normal del correo (MailView) y la
 * carpeta Bandeja de salida (components/mail/salida/). En el celular no se muestra (max-md:hidden).
 */
import type React from 'react';
import { useMailStore } from '../../store/mailStore';

export function ListResizeHandle() {
  const setMessageListWidth = useMailStore(s => s.setMessageListWidth);
  const onMouseDown = (e: React.MouseEvent) => {
    e.preventDefault();
    const startX = e.clientX;
    const startW = useMailStore.getState().messageListWidth;
    const onMove = (ev: MouseEvent) => setMessageListWidth(startW + (ev.clientX - startX));
    const onUp = () => {
      window.removeEventListener('mousemove', onMove);
      window.removeEventListener('mouseup', onUp);
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
    };
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';
    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup', onUp);
  };
  return (
    <div
      onMouseDown={onMouseDown}
      title="Arrastra para ajustar el ancho de la lista"
      className="w-[5px] shrink-0 cursor-col-resize bg-transparent hover:bg-[#0078d4]/40 active:bg-[#0078d4]/60 transition-colors max-md:hidden"
    />
  );
}
