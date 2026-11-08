import { megasTeams, useManifiestoTeams } from '../../lib/teamsWindows';

/** Sección «Teams para Windows» (05/11/2026), debajo de la app de Android.
 *  Lee el manifiesto que publica el equipo de la app (`lib/teamsWindows.ts`, el mismo que usa la app
 *  para actualizarse sola). Si no hay versión publicada, no aparece. */
export default function DescargaTeamsWindows() {
  const m = useManifiestoTeams();

  if (!m) return null;
  const nombre = m.nombre || 'Teams';
  const detalle = [`Versión ${m.version}`, megasTeams(m.tamano), m.fecha].filter(Boolean).join(' · ');

  return (
    <div className="bg-white border rounded-lg p-4">
      <h4 className="font-medium mb-2">💻 {nombre} para Windows</h4>
      <p className="text-sm text-[#605e5c] mb-3">
        Chat, llamadas, reuniones, correo y Raíces en una sola aplicación para la computadora. Entra con su correo y su contraseña.
      </p>
      <ol className="text-sm text-[#323130] list-decimal ml-5 mb-3 space-y-1">
        <li>Pulse <strong>Descargar {nombre}</strong> desde la computadora con Windows.</li>
        <li>Abra el archivo descargado. Si Windows muestra «Windows protegió su PC», pulse <strong>Más información → Ejecutar de todas formas</strong>.</li>
        <li>Al terminar, ábralo desde el escritorio e ingrese con su correo.</li>
      </ol>
      <div className="flex flex-wrap items-center gap-3">
        <a href={m.url} download
          className="inline-block bg-[#0078d4] text-white px-4 py-2 rounded hover:bg-[#106ebe] text-sm">
          Descargar {nombre}
        </a>
        <a href="/app" target="_blank" rel="noopener noreferrer" className="text-sm text-[#0078d4] hover:underline">
          Página de instalación y ayuda
        </a>
      </div>
      <p className="text-xs text-gray-400 mt-2">{detalle}. La aplicación se actualiza sola cuando publicamos una versión nueva.</p>
    </div>
  );
}
