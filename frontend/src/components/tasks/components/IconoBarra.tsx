// Íconos de la barra lateral de Tareas (listas inteligentes, listas y grupos).
export function SidebarIcon({ icon, size = 18 }: { icon: string; size?: number }) {
  const s = { width: size, height: size };
  switch (icon) {
    case 'sun':
      return (
        <svg style={s} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8}>
          <circle cx="12" cy="12" r="5" /><path d="M12 1v2m0 18v2M4.22 4.22l1.42 1.42m12.72 12.72l1.42 1.42M1 12h2m18 0h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42" />
        </svg>
      );
    case 'star':
      return (
        <svg style={s} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8}>
          <path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z" />
        </svg>
      );
    case 'calendar':
      return (
        <svg style={s} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8}>
          <rect x="3" y="4" width="18" height="18" rx="2" /><path d="M16 2v4M8 2v4M3 10h18" />
        </svg>
      );
    case 'person':
      return (
        <svg style={s} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8}>
          <path d="M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2" /><circle cx="12" cy="7" r="4" />
        </svg>
      );
    case 'flag':
      return (
        <svg style={s} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8}>
          <path d="M4 15s1-1 4-1 5 2 8 2 4-1 4-1V3s-1 1-4 1-5-2-8-2-4 1-4 1z" /><line x1="4" y1="22" x2="4" y2="15" />
        </svg>
      );
    case 'home':
      return (
        <svg style={s} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8}>
          <path d="M3 9l9-7 9 7v11a2 2 0 01-2 2H5a2 2 0 01-2-2z" /><polyline points="9 22 9 12 15 12 15 22" />
        </svg>
      );
    case 'list':
      return (
        <svg style={s} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8}>
          <line x1="8" y1="6" x2="21" y2="6" /><line x1="8" y1="12" x2="21" y2="12" /><line x1="8" y1="18" x2="21" y2="18" />
          <line x1="3" y1="6" x2="3.01" y2="6" /><line x1="3" y1="12" x2="3.01" y2="12" /><line x1="3" y1="18" x2="3.01" y2="18" />
        </svg>
      );
    case 'folder':
      return (
        <svg style={s} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8}>
          <path d="M3 7a2 2 0 012-2h4l2 2h8a2 2 0 012 2v8a2 2 0 01-2 2H5a2 2 0 01-2-2z" />
        </svg>
      );
    case 'list-plus':
      return (
        <svg style={s} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
          <line x1="4" y1="6" x2="15" y2="6" /><line x1="4" y1="12" x2="12" y2="12" /><line x1="4" y1="18" x2="10" y2="18" />
          <line x1="18" y1="13" x2="18" y2="21" /><line x1="14" y1="17" x2="22" y2="17" />
        </svg>
      );
    case 'folder-plus':
      return (
        <svg style={s} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8}>
          <path d="M3 7a2 2 0 012-2h4l2 2h8a2 2 0 012 2v8a2 2 0 01-2 2H5a2 2 0 01-2-2z" />
          <line x1="12" y1="10" x2="12" y2="16" /><line x1="9" y1="13" x2="15" y2="13" />
        </svg>
      );
    default:
      return (
        <svg style={s} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8}>
          <circle cx="12" cy="12" r="10" />
        </svg>
      );
  }
}
