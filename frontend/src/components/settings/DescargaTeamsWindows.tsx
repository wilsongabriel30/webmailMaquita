import { useEffect, useState } from 'react';

/** Sección «Teams Maquita para Windows» (05/11/2026), junto a la app de Android.
 *  Lee el manifiesto que publica el equipo de la app (`/static/teams/teams-windows-version.json`,
 *  el mismo que usa la app para actualizarse sola). Si no hay versión publicada, no aparece. */
interface Manifiesto { version: string; url: string; tamano?: number; fecha?: string; }

function megas(bytes?: number): string {
  return bytes ? `${Math.round(bytes / 1048576)} MB` : '';
}

export default function DescargaTeamsWindows() {
  const [m, setM] = useState<Manifiesto | null>(null);

  useEffect(() => {
    fetch('/static/teams/teams-windows-version.json', { cache: 'no-store' })
      .then(r => (r.ok ? r.json() : null))
      .then(d => { if (d && d.version && d.url) setM(d); })
      .catch(() => { /* sin manifiesto: la sección no se muestra */ });
  }, []);

  if (!m) return null;
  const detalle = [`Versión ${m.version}`, megas(m.tamano), m.fecha].filter(Boolean).join(' · ');

  return (
    <div className="bg-white border rounded-lg p-4">
      <h4 className="font-medium mb-2">💻 Teams Maquita para Windows</h4>
      <p className="text-sm text-[#605e5c] mb-3">
        Chat, llamadas, reuniones, correo y Raíces en una sola aplicación para la computadora. Entra con su correo y su contraseña.
      </p>
      <ol className="text-sm text-[#323130] list-decimal ml-5 mb-3 space-y-1">
        <li>Pulse <strong>Descargar Teams Maquita</strong> desde la computadora con Windows.</li>
        <li>Abra el archivo descargado. Si Windows muestra «Windows protegió su PC», pulse <strong>Más información → Ejecutar de todas formas</strong>.</li>
        <li>Al terminar, ábralo desde el escritorio e ingrese con su correo.</li>
      </ol>
      <div className="flex flex-wrap items-center gap-3">
        <a href={m.url} download
          className="inline-block bg-[#0078d4] text-white px-4 py-2 rounded hover:bg-[#106ebe] text-sm">
          Descargar Teams Maquita
        </a>
        <a href="/app" target="_blank" rel="noopener noreferrer" className="text-sm text-[#0078d4] hover:underline">
          Página de instalación y ayuda
        </a>
      </div>
      <p className="text-xs text-gray-400 mt-2">{detalle}. La aplicación se actualiza sola cuando publicamos una versión nueva.</p>
    </div>
  );
}
