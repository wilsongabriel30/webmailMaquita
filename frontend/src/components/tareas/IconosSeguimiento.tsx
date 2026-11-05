// Íconos de línea de Seguimiento (en lugar de emojis): mismo trazo que el resto de Tareas y heredan el color del texto.
import type { ReactNode } from 'react';

function Icono({ children, tam = 13 }: { children: ReactNode; tam?: number }) {
  return (
    <svg aria-hidden="true" width={tam} height={tam} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8}
      strokeLinecap="round" strokeLinejoin="round" style={{ flexShrink: 0, verticalAlign: '-2px' }}>
      {children}
    </svg>
  );
}

export const IcoCalendario = () => <Icono><path d="M5 4h14a2 2 0 012 2v13a2 2 0 01-2 2H5a2 2 0 01-2-2V6a2 2 0 012-2zM3 9h18M8 2v4M16 2v4" /></Icono>;
export const IcoPersona = () => <Icono><circle cx="12" cy="8" r="4" /><path d="M4 21c0-4 4-6 8-6s8 2 8 6" /></Icono>;
export const IcoPasos = () => <Icono><rect x="3" y="3" width="18" height="18" rx="2" /><path d="M8 12l3 3 5-6" /></Icono>;
export const IcoComentario = () => <Icono><path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z" /></Icono>;
export const IcoClip = () => <Icono><path d="M21.44 11.05l-9.19 9.19a6 6 0 01-8.49-8.49l9.19-9.19a4 4 0 015.66 5.66l-9.2 9.19a2 2 0 01-2.83-2.83l8.49-8.48" /></Icono>;
export const IcoRepetir = () => <Icono><path d="M17 2l4 4-4 4M3 11V9a3 3 0 013-3h15M7 22l-4-4 4-4M21 13v2a3 3 0 01-3 3H3" /></Icono>;
export const IcoEscalada = () => <Icono><path d="M12 19V5M5 12l7-7 7 7" /></Icono>;
export const IcoLista = () => <Icono tam={15}><path d="M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01" /></Icono>;
export const IcoTablero = () => <Icono tam={15}><rect x="3" y="3" width="7" height="18" rx="1" /><rect x="14" y="3" width="7" height="11" rx="1" /></Icono>;

/** Punto de color (semáforo del resumen), sin carácter «●». */
export const Punto = ({ color }: { color: string }) => (
  <span aria-hidden="true" style={{ display: 'inline-block', width: 8, height: 8, borderRadius: '50%', background: color, marginRight: 5, verticalAlign: '1px' }} />
);

/** Fila «ícono + texto» de los datos de una tarjeta. */
export const Dato = ({ icono, children, title }: { icono: ReactNode; children: ReactNode; title?: string }) => (
  <span title={title} style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>{icono}{children}</span>
);
