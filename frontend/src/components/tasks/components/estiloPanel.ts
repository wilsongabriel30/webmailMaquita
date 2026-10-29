// Estilos compartidos por las secciones del panel de detalle de una tarea. Desde la F5 el panel va como en Outlook:
// tarjetas sobre un fondo rosado claro, cada una con sus filas («Recordarme», «Hoy», «Repetir»… comparten tarjeta).
import type { CSSProperties } from 'react';
import { COLORS } from '../types';

/** Fondo del panel y de sus tarjetas (los tonos del panel de Outlook). */
export const FONDO_PANEL = '#fbf3f4';
export const FONDO_TARJETA = '#f6e9eb';
export const LINEA_TARJETA = '#ead7da';

export const tarjeta: CSSProperties = {
  background: FONDO_TARJETA, borderRadius: 4, margin: '0 12px 8px', display: 'flex', flexDirection: 'column',
};

/** Una fila dentro de una tarjeta. */
export const seccion: CSSProperties = {
  padding: '14px 16px', display: 'flex', flexDirection: 'column', alignItems: 'flex-start', gap: 0,
  fontSize: 14, color: COLORS.text, position: 'relative',
};

export const filaSeccion: CSSProperties = {
  display: 'flex', alignItems: 'center', gap: 14, width: '100%', cursor: 'pointer',
  background: 'none', border: 'none', padding: 0, fontSize: 14, fontFamily: 'inherit', textAlign: 'left', color: COLORS.text,
};

export const desplegable: CSSProperties = {
  marginTop: 8, marginLeft: 32, background: 'white', border: `1px solid ${COLORS.border}`,
  borderRadius: 6, boxShadow: '0 4px 12px rgba(0,0,0,0.15)', padding: 4, zIndex: 10,
};

export const opcion: CSSProperties = {
  display: 'block', width: '100%', textAlign: 'left', padding: '8px 12px', fontSize: 13, cursor: 'pointer',
  borderRadius: 4, background: 'none', border: 'none', fontFamily: 'inherit', color: COLORS.text,
};

export const quitar: CSSProperties = {
  marginLeft: 'auto', background: 'none', border: 'none', cursor: 'pointer', color: '#d13438', fontSize: 12, fontFamily: 'inherit',
};
