/**
 * Aviso de «correo no entregado» explicado en español llano (12/11/2026).
 *
 * El servidor devuelve estos avisos en inglés y con códigos («452-4.2.2 … gsmtp»). Aquí, encima del
 * aviso original, se dice por cada destinatario qué pasó, de quién es el problema y qué hacer. El
 * detalle técnico queda plegado, para poder enviarlo a Tecnología.
 */
import React from 'react';

export interface DestinatarioRebote {
  correo: string; tipo: string; definitivo: boolean; titulo: string; que_paso: string; que_hacer: string; detalle_tecnico: string;
}
export interface Rebote { destinatarios: DestinatarioRebote[]; original?: { asunto?: string; fecha?: string } }

const COLOR: Record<string, { fondo: string; borde: string; texto: string }> = {
  demorado: { fondo: '#fff8e1', borde: '#f2c94c', texto: '#7a5b00' },
  normal: { fondo: '#fdf3f2', borde: '#f1b0aa', texto: '#8e1d14' },
};

export const AvisoRebote: React.FC<{ rebote: Rebote }> = ({ rebote }) => {
  const [abierto, setAbierto] = React.useState<string | null>(null);
  if (!rebote?.destinatarios?.length) return null;
  const asunto = rebote.original?.asunto;
  return (
    <div role="alert" aria-label="Correo no entregado" style={{ display: 'grid', gap: 10 }}>
      {rebote.destinatarios.map((d) => {
        const c = d.definitivo ? COLOR.normal : COLOR.demorado;
        return (
          <div key={d.correo} style={{ background: c.fondo, border: `1px solid ${c.borde}`, borderRadius: 8, padding: '12px 14px', color: '#323130' }}>
            <div style={{ fontSize: 14, fontWeight: 700, color: c.texto }}>{d.titulo}</div>
            <div style={{ fontSize: 13, marginTop: 4 }}>
              {d.definitivo ? 'No se entregó' : 'Aún no se entrega'} su correo{asunto ? <> «<b>{asunto}</b>»</> : null} a <b>{d.correo}</b>.
            </div>
            <div style={{ fontSize: 13, marginTop: 6 }}><b>Qué pasó:</b> {d.que_paso}</div>
            <div style={{ fontSize: 13, marginTop: 4 }}><b>Qué hacer:</b> {d.que_hacer}</div>
            <button type="button" onClick={() => setAbierto(abierto === d.correo ? null : d.correo)} aria-expanded={abierto === d.correo}
              style={{ marginTop: 8, background: 'none', border: 'none', padding: 0, color: '#0078d4', fontSize: 12, cursor: 'pointer' }}>
              {abierto === d.correo ? 'Ocultar el detalle técnico' : 'Ver el detalle técnico (para Tecnología)'}
            </button>
            {abierto === d.correo && (
              <div style={{ marginTop: 6, fontSize: 11, fontFamily: 'monospace', color: '#605e5c', wordBreak: 'break-word', background: '#fff', border: '1px solid #edebe9', borderRadius: 4, padding: '6px 8px' }}>
                {d.detalle_tecnico || 'Sin detalle.'}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
};
