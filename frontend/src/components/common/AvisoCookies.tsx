/**
 * Aviso de cookies (Ley Orgánica de Protección de Datos Personales del Ecuador, LOPDP).
 *
 * El correo web solo usa cookies estrictamente necesarias: sesión (access_token, refresh_token),
 * dispositivo de confianza para el segundo factor y, dentro del cliente de escritorio, la
 * preferencia de modo app. No hay cookies de publicidad, analítica ni de terceros, así que no
 * se pide consentimiento: se informa y se enlaza la política. «Entendido» guarda la lectura
 * en localStorage (no en una cookie) para no volver a mostrarlo en este navegador.
 */
import { useState } from 'react';

const CLAVE = 'maquita_aviso_cookies';

function yaLeido(): boolean {
  try { return localStorage.getItem(CLAVE) === '1'; } catch { return false; }
}

export function AvisoCookies() {
  const [visible, setVisible] = useState(() => !yaLeido());
  if (!visible) return null;
  const cerrar = () => {
    try { localStorage.setItem(CLAVE, '1'); } catch { /* sin almacenamiento: se mostrará otra vez */ }
    setVisible(false);
  };
  return (
    <div role="region" aria-label="Aviso de cookies"
      className="fixed bottom-0 inset-x-0 z-[9998] px-4 py-3 bg-[#323130] text-white text-[13px] shadow-[0_-2px_8px_rgba(0,0,0,.25)]">
      <div className="max-w-[960px] mx-auto flex flex-col sm:flex-row sm:items-center gap-2 sm:gap-4">
        <p className="flex-1 leading-snug">
          Este correo usa solo cookies <strong>necesarias</strong> para mantener tu sesión y protegerla
          (segundo factor y dispositivo de confianza). No usamos cookies de publicidad, seguimiento ni de
          terceros.{' '}
          <a href="/webmail/privacidad" className="underline text-[#9cc9f0] hover:text-white">
            Política de privacidad y cookies
          </a>
        </p>
        <button type="button" onClick={cerrar}
          className="shrink-0 self-end sm:self-auto px-4 py-1.5 rounded bg-white text-[#323130] font-semibold hover:bg-[#edebe9]">
          Entendido
        </button>
      </div>
    </div>
  );
}
