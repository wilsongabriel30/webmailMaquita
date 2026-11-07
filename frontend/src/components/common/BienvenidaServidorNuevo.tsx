/**
 * Bienvenida al servidor nuevo tras una migración de correo (03/11/2026).
 *
 * El servidor decide si corresponde (dominio, fecha del cambio y los días contados desde el
 * primer ingreso de cada persona: ver backend/app/bienvenida). Aquí solo se muestra, una vez
 * por sesión del navegador mientras dure ese plazo.
 */
import { useEffect, useState } from 'react';
import { api } from '../../api/client';

const CLAVE = 'bienvenida_servidor_nuevo_vista';

interface Estado { mostrar: boolean; dia?: number; dias?: number }

function yaVista(): boolean {
  try { return sessionStorage.getItem(CLAVE) === '1'; } catch { return false; }
}

export function BienvenidaServidorNuevo() {
  const [estado, setEstado] = useState<Estado | null>(null);

  useEffect(() => {
    if (yaVista()) return;
    api.get<Estado>('/bienvenida')
      .then((e) => { if (e.mostrar) setEstado(e); })
      .catch(() => { /* sin bienvenida: no estorba el ingreso */ });
  }, []);

  if (!estado) return null;
  const cerrar = () => {
    try { sessionStorage.setItem(CLAVE, '1'); } catch { /* se mostrará otra vez */ }
    setEstado(null);
  };

  return (
    <div role="dialog" aria-modal="true" aria-labelledby="bienvenida-titulo"
      className="fixed inset-0 z-[9999] flex items-center justify-center bg-black/50 px-4"
      onKeyDown={(e) => { if (e.key === 'Escape') cerrar(); }}>
      <div className="w-full max-w-[560px] rounded-lg bg-white shadow-xl p-6 text-[14px] text-[#323130] leading-relaxed">
        <h2 id="bienvenida-titulo" className="text-[20px] font-semibold text-[#0078d4] mb-3">
          ¡Bienvenido a su nuevo correo!
        </h2>
        <p className="mb-3">
          Desde ahora su correo funciona en el servidor nuevo. Su dirección y su clave son las mismas.
        </p>
        <ul className="list-disc pl-5 mb-3 space-y-1">
          <li>Sus correos y carpetas del servidor anterior ya están aquí.</li>
          <li>Si usa Outlook o el celular y le piden la clave, escriba la misma de siempre.</li>
          <li>En <strong>Configuración</strong> encontrará los datos para configurar Outlook y el celular.</li>
        </ul>
        <p className="mb-3">
          Es una plataforma propia, en mejora continua. Si algo no funciona como espera, avise al
          Departamento de Tecnología con una captura de pantalla y la hora: así lo corregimos pronto.
        </p>
        <div className="flex items-center justify-between gap-3 mt-4">
          <span className="text-[12px] text-[#605e5c]">
            Este aviso se muestra durante sus primeros {estado.dias} días (día {estado.dia} de {estado.dias}).
          </span>
          <button type="button" autoFocus onClick={cerrar}
            className="shrink-0 px-5 py-2 rounded bg-[#0078d4] text-white font-semibold hover:bg-[#106ebe]">
            Empezar
          </button>
        </div>
      </div>
    </div>
  );
}
