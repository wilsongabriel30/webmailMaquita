// Estilos compartidos por las secciones del panel de detalle de una tarea.
import type { CSSProperties } from 'react';
import { COLORS } from '../types';

export const seccion: CSSProperties = {
  padding: '12px 20px', borderBottom: `1px solid ${COLORS.border}`,
  display: 'flex', flexDirection: 'column', alignItems: 'flex-start', gap: 0,
  fontSize: 14, color: COLORS.text, position: 'relative',
};

export const filaSeccion: CSSProperties = {
  display: 'flex', alignItems: 'center', gap: 12, width: '100%', cursor: 'pointer',
  background: 'none', border: 'none', padding: 0, fontSize: 14, fontFamily: 'inherit', textAlign: 'left', color: COLORS.text,
};

export const desplegable: CSSProperties = {
  marginTop: 8, marginLeft: 30, background: 'white', border: `1px solid ${COLORS.border}`,
  borderRadius: 6, boxShadow: '0 4px 12px rgba(0,0,0,0.15)', padding: 4, zIndex: 10,
};

export const opcion: CSSProperties = {
  display: 'block', width: '100%', textAlign: 'left', padding: '8px 12px', fontSize: 13, cursor: 'pointer',
  borderRadius: 4, background: 'none', border: 'none', fontFamily: 'inherit', color: COLORS.text,
};

export const quitar: CSSProperties = {
  marginLeft: 'auto', background: 'none', border: 'none', cursor: 'pointer', color: '#d13438', fontSize: 12, fontFamily: 'inherit',
};
