/**
 * CerrarSesiones.tsx — «Cerrar todas las sesiones» (L-01, mínimo).
 *
 * Llama a POST /api/auth/logout-all: sube la generación de autenticación del usuario,
 * revoca todos los refresh y cierra webmail, app y chat en todos los dispositivos,
 * incluido este. Después se recarga: el webmail vuelve a la pantalla de entrada.
 */

import { useState } from 'react';

export function CerrarSesiones() {
  const [trabajando, setTrabajando] = useState(false);
  const [error, setError] = useState('');

  const cerrarTodas = async () => {
    if (!window.confirm('Se cerrará tu sesión en todos los dispositivos, incluido este. ¿Continuar?')) return;
    setTrabajando(true);
    setError('');
    try {
      const r = await fetch('/api/auth/logout-all', { method: 'POST', credentials: 'include' });
      if (!r.ok) throw new Error('No se pudo cerrar las sesiones');
      window.location.reload();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'No se pudo cerrar las sesiones');
      setTrabajando(false);
    }
  };

  return (
    <div className="mt-6 border-t border-[#edebe9] pt-4">
      <h3 className="text-[13px] font-semibold text-[#323130]">Sesiones abiertas</h3>
      <p className="mt-1 text-[12px] text-[#605e5c]">
        Si perdiste un equipo o sospechas que alguien más entró a tu cuenta, cierra todas las
        sesiones: webmail, app y chat en todos los dispositivos, incluido este.
      </p>
      {error && <p className="mt-2 text-[12px] text-[#d13438]">{error}</p>}
      <button
        type="button"
        onClick={cerrarTodas}
        disabled={trabajando}
        className="mt-3 rounded border border-[#d13438] px-3 py-[5px] text-[13px] text-[#d13438] hover:bg-[#fde7e9] disabled:opacity-50"
      >
        {trabajando ? 'Cerrando…' : 'Cerrar todas las sesiones'}
      </button>
    </div>
  );
}
