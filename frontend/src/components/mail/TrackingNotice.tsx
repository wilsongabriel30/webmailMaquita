/**
 * TrackingNotice — aviso de enlaces con rastreo de terceros.
 *
 * QUÉ MUESTRA
 * -----------
 * Cuando un correo trae enlaces que pasan por un servicio de rastreo externo
 * (Mailchimp, HubSpot, SendGrid...), avisa al usuario de lo que ocurre:
 *
 *  · Si es PUBLICIDAD      → ofrece marcar el correo como spam.
 *  · Si es TRANSACCIONAL   → solo recomienda comprobar el destino, porque
 *                            puede ser una factura o una clave esperada.
 *
 * Los enlaces que SÍ se pueden limpiar (Amazon SES, Postmark) ya vienen
 * desenvueltos desde el backend y no generan aviso: en esos el usuario va
 * directo al destino real.
 *
 * POR QUÉ ESTÁ EN SU PROPIO ARCHIVO
 * ---------------------------------
 * MessageView.tsx supera las 1500 líneas. La norma del equipo es no engordar
 * los módulos ya grandes, sino extraer lo nuevo a su propio archivo.
 * Aquí solo se añade el import y una línea de uso.
 *
 * Backend: app/mail/rendering/tracker_info.py
 * Doc: webmail/desenvoltura-enlaces-rastreo-20260824.md
 */

interface TrackingNoticeData {
  hay_rastreo: boolean;
  es_publicidad: boolean;
  servicios: string[];
  mensaje: string;
}

interface Props {
  /** Viene del backend en la respuesta del mensaje (campo tracking_notice). */
  notice?: TrackingNoticeData | null;
  /** Se invoca al pulsar "Marcar como spam". Solo se usa si es publicidad. */
  onMarkSpam?: () => void;
  /** Deshabilita el botón mientras la acción está en curso. */
  markingSpam?: boolean;
}

export default function TrackingNotice({ notice, onMarkSpam, markingSpam }: Props) {
  // Sin rastreo detectado: no se muestra nada. Es el caso mayoritario.
  if (!notice?.hay_rastreo) return null;

  // La publicidad se resalta en ámbar; lo transaccional, en azul informativo,
  // para que no parezca una alerta de peligro (puede ser un correo esperado).
  const esPublicidad = notice.es_publicidad;
  const fondo = esPublicidad ? '#fff4ce' : '#eff6fc';
  const colorIcono = esPublicidad ? '#797775' : '#0078d4';

  return (
    <div
      style={{
        marginTop: 12,
        padding: '8px 12px',
        background: fondo,
        borderRadius: 4,
        display: 'flex',
        alignItems: 'center',
        gap: 10,
        fontSize: 13,
        color: '#323130',
      }}
    >
      <svg width="16" height="16" viewBox="0 0 16 16" fill={colorIcono} style={{ flexShrink: 0 }}>
        <path d="M8 1a7 7 0 100 14A7 7 0 008 1zm0 10.5a.75.75 0 110-1.5.75.75 0 010 1.5zM8.75 4v5h-1.5V4h1.5z" />
      </svg>

      <span>{notice.mensaje}</span>

      {/* El botón de spam solo aparece en publicidad: nunca en correos
          transaccionales, que el usuario puede estar esperando. */}
      {esPublicidad && onMarkSpam && (
        <button
          onClick={onMarkSpam}
          disabled={markingSpam}
          style={{
            background: '#a4262c',
            color: '#fff',
            border: 'none',
            borderRadius: 4,
            padding: '4px 12px',
            fontSize: 12,
            cursor: markingSpam ? 'default' : 'pointer',
            fontWeight: 600,
            marginLeft: 'auto',
            opacity: markingSpam ? 0.6 : 1,
            whiteSpace: 'nowrap',
          }}
        >
          {markingSpam ? 'Marcando...' : 'Marcar como spam'}
        </button>
      )}
    </div>
  );
}
