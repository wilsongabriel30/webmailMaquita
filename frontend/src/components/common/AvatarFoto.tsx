/**
 * AvatarFoto — círculo con la foto de perfil o, si no hay (o falla la carga), las iniciales (09/11/2026).
 *
 * Se usa en la burbuja superior, la lista de correos, el correo abierto y el hilo, para que la
 * foto del directorio (Raíces o propia) se vea igual en todas partes. Solo pinta; el color de
 * fondo y las iniciales los decide quien lo usa. La imagen se carga en diferido y sin enviar
 * «Referer» (la foto vive en otro dominio, gestion.example.org).
 */
import { useState } from 'react';

export interface AvatarFotoProps {
  url?: string;
  initials: string;
  /** Lado en píxeles. */
  size: number;
  /** Fondo del círculo cuando se muestran iniciales. */
  color?: string;
  className?: string;
  /** Tamaño de letra de las iniciales (por defecto proporcional al lado). */
  fontSize?: number;
  title?: string;
}

export function AvatarFoto({ url, initials, size, color = '#0078d4', className = '', fontSize, title }: AvatarFotoProps) {
  // Se recuerda la URL que falló: si cambia la URL se vuelve a intentar sin necesidad de un efecto.
  const [urlFallida, setUrlFallida] = useState<string | undefined>(undefined);
  const conFoto = !!url && url !== urlFallida;
  return (
    <span
      title={title}
      className={`inline-flex items-center justify-center rounded-full overflow-hidden shrink-0 font-semibold text-white select-none ${className}`}
      style={{ width: size, height: size, background: conFoto ? '#e1dfdd' : color, fontSize: fontSize ?? Math.max(9, Math.round(size * 0.36)) }}
    >
      {conFoto ? (
        <img
          src={url}
          alt=""
          width={size}
          height={size}
          loading="lazy"
          decoding="async"
          referrerPolicy="no-referrer"
          className="w-full h-full object-cover"
          onError={() => setUrlFallida(url)}
        />
      ) : (
        <span aria-hidden="true">{initials}</span>
      )}
    </span>
  );
}

export default AvatarFoto;
