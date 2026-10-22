import { useState } from 'react';

// Piezas de la pantalla de entrada que salen de /api/branding según el dominio por el que se
// entra (mail.<dominio>, webmail.<dominio>): la bienvenida bajo el logo y la ayuda de
// «¿Olvidaste tu contraseña?». Sin datos del servidor quedan textos neutros.

/** «Correo de <organización>» bajo el logo; nada si el servidor no lo da. */
export function BienvenidaEntrada({ texto, color }: { texto?: string; color: string }) {
  if (!texto) return null;
  return (
    <p className="text-sm font-medium mb-2" style={{ color }}>
      {texto}
    </p>
  );
}

/** Enlace «¿Olvidaste tu contraseña?»: dice a quién escribir (correo del administrador del dominio). */
export function OlvidoContrasena({ contacto, dominio, color }: { contacto?: string; dominio?: string; color: string }) {
  const [abierto, setAbierto] = useState(false);
  const asunto = encodeURIComponent(`Restablecer mi contraseña del correo${dominio ? ' de ' + dominio : ''}`);
  return (
    <div className="mt-3 text-center">
      <button type="button" onClick={() => setAbierto(!abierto)} aria-expanded={abierto}
        className="text-sm hover:underline" style={{ color }}>
        ¿Olvidaste tu contraseña?
      </button>
      {abierto && (
        <p className="text-xs mt-2" style={{ color: '#605e5c' }}>
          {contacto ? (
            <>
              Escribe a <a href={`mailto:${contacto}?subject=${asunto}`} className="underline" style={{ color }}>{contacto}</a>{' '}
              (desde otra cuenta de correo) para que restablezcan tu contraseña.
            </>
          ) : (
            <>Pide a quien administra el correo de tu organización que restablezca tu contraseña.</>
          )}
        </p>
      )}
    </div>
  );
}
