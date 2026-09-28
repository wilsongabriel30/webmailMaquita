/**
 * Aviso de imágenes remotas bloqueadas, con el botón para cargarlas.
 * Se usa en el mensaje suelto y en cada mensaje de una conversación.
 */
interface Props {
  cantidad: number;
  cargando: boolean;
  error?: boolean;
  onCargar: () => void;
}

export default function AvisoImagenesBloqueadas({ cantidad, cargando, error, onCargar }: Props) {
  const plural = cantidad > 1;
  return (
    <div style={{
      marginTop: 12, padding: '8px 12px', background: '#fff4ce', borderRadius: 4,
      display: 'flex', alignItems: 'center', gap: 10, fontSize: 13, color: '#323130',
    }}>
      <svg width="16" height="16" viewBox="0 0 16 16" fill="#797775" style={{ flexShrink: 0 }}>
        <path d="M8 1a7 7 0 100 14A7 7 0 008 1zm0 10.5a.75.75 0 110-1.5.75.75 0 010 1.5zM8.75 4v5h-1.5V4h1.5z"/>
      </svg>
      <span>
        {error
          ? 'No se pudieron cargar las imágenes. Inténtalo de nuevo.'
          : `Se bloque${plural ? 'aron' : 'ó'} ${cantidad} imagen${plural ? 'es' : ''} remota${plural ? 's' : ''} por seguridad.`}
      </span>
      <button
        onClick={onCargar}
        disabled={cargando}
        style={{
          background: '#0078d4', color: '#fff', border: 'none', borderRadius: 4,
          padding: '4px 12px', fontSize: 12, cursor: cargando ? 'default' : 'pointer',
          fontWeight: 600, marginLeft: 'auto', opacity: cargando ? 0.6 : 1, flexShrink: 0,
        }}
      >
        {cargando ? 'Cargando...' : 'Cargar imágenes'}
      </button>
    </div>
  );
}
