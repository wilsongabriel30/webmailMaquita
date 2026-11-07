// Íconos del menú de una lista en la barra (como en To Do, F5).
const TRAZOS: Record<string, string> = {
  compartir: 'M15 19v-1a4 4 0 00-4-4H7a4 4 0 00-4 4v1M9 10a3 3 0 100-6 3 3 0 000 6zM19 13v6M16 16h6',
  moverA: 'M5 3h9l4 4v5M5 3v18h7M5 3H4M14 3v4h4M16 15l-3 3 3 3M13 18h8',
  quitarGrupo: 'M5 3h9l4 4v5M5 3v18h7M14 3v4h4M17 15l3 3-3 3M20 18h-8',
  abajo: 'M12 4v16M6 14l6 6 6-6',
  arriba: 'M12 20V4M6 10l6-6 6 6',
  duplicar: 'M8 8V4a1 1 0 011-1h10a1 1 0 011 1v12a1 1 0 01-1 1h-4M5 7h9a1 1 0 011 1v12a1 1 0 01-1 1H5a1 1 0 01-1-1V8a1 1 0 011-1z',
  imprimir: 'M7 9V3h10v6M7 17H5a2 2 0 01-2-2v-4a2 2 0 012-2h14a2 2 0 012 2v4a2 2 0 01-2 2h-2M7 14h10v7H7z',
  eliminar: 'M4 6h16M9 6V4h6v2M6 6l1 14a1 1 0 001 1h8a1 1 0 001-1l1-14M10 10v7M14 10v7',
  salir: 'M15 3h4a2 2 0 012 2v14a2 2 0 01-2 2h-4M10 17l-5-5 5-5M5 12h12',
  renombrar: 'M4 20h4L18.5 9.5a2.1 2.1 0 00-3-3L5 17v3zM14.5 7.5l2 2',
};

export function IconoMenuLista({ nombre }: { nombre: keyof typeof TRAZOS | string }) {
  return (
    <svg aria-hidden="true" width={18} height={18} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5}
      strokeLinecap="round" strokeLinejoin="round" style={{ flexShrink: 0 }}>
      <path d={TRAZOS[nombre] || ''} />
    </svg>
  );
}
