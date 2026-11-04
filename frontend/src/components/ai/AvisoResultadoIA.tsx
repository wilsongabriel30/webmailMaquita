/**
 * Aviso amable cuando una función de IA termina sin resultado o falla (04/11/2026).
 *
 * Antes «Respuesta IA» y «Pregúntale a tu correo» volvían a la pantalla de partida sin decir
 * nada, y la persona no sabía si había funcionado. Se distingue «no hubo resultado» de «falló»
 * y se ofrece «Reintentar». Cancelar no muestra este aviso: lo decidió la persona.
 * Revisión independiente de la interfaz, hallazgos 8 y 9.
 */
export type ResultadoIA = 'vacio' | 'error';

interface Props {
  tipo: ResultadoIA;
  /** Texto cuando el servicio respondió, pero sin contenido. */
  textoVacio: string;
  /** Texto cuando la petición falló. */
  textoError: string;
  onReintentar?: () => void;
  onCerrar?: () => void;
}

export function AvisoResultadoIA({ tipo, textoVacio, textoError, onReintentar, onCerrar }: Props) {
  const esError = tipo === 'error';
  return (
    <div role={esError ? 'alert' : 'status'} aria-live="polite"
      style={{
        padding: '12px 24px', borderTop: '1px solid #edebe9', flexShrink: 0,
        background: esError ? '#fdf3f4' : '#f5f9fd',
        display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap',
      }}>
      <p style={{ margin: 0, flex: '1 1 220px', minWidth: 0, fontSize: 15, lineHeight: 1.45, color: esError ? '#a4262c' : '#201f1e' }}>
        {esError ? textoError : textoVacio}
      </p>
      {onReintentar && (
        <button type="button" onClick={onReintentar}
          style={{ minHeight: 40, padding: '6px 16px', fontSize: 15, fontWeight: 600, background: '#0078d4', color: '#fff', border: 'none', borderRadius: 6, cursor: 'pointer' }}>
          Reintentar
        </button>
      )}
      {onCerrar && (
        <button type="button" onClick={onCerrar} aria-label="Cerrar aviso" title="Cerrar aviso"
          style={{ minHeight: 40, minWidth: 40, padding: '6px 10px', fontSize: 15, background: '#fff', color: '#323130', border: '1px solid #8a8886', borderRadius: 6, cursor: 'pointer' }}>
          ✕
        </button>
      )}
    </div>
  );
}
