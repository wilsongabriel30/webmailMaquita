import { textoTamano, urlApk, useManifiestoApp } from '../../lib/appAndroid';

/** Sección «App para Android» (AM-11): solo aparece si el servidor tiene una versión publicada. */
export default function DescargaAppAndroid() {
  const m = useManifiestoApp();
  if (!m) return null;
  const detalle = [`Versión ${m.versionName}`, textoTamano(m), m.fecha].filter(Boolean).join(' · ');

  return (
    <div className="bg-white border rounded-lg p-4">
      <h4 className="font-medium mb-2">🤖 App para Android</h4>
      <p className="text-sm text-[#605e5c] mb-3">
        La aplicación oficial entra con su correo y su contraseña y avisa de los mensajes nuevos.
      </p>
      <ol className="text-sm text-[#323130] list-decimal ml-5 mb-3 space-y-1">
        <li>Pulse <strong>Descargar app para Android</strong> desde el teléfono.</li>
        <li>Cuando Android lo pida, permita «instalar aplicaciones desconocidas» para el navegador.</li>
        <li>Abra el archivo descargado e instale.</li>
      </ol>
      <button
        onClick={() => window.open(urlApk(), '_blank')}
        className="inline-block bg-[#0078d4] text-white px-4 py-2 rounded hover:bg-[#106ebe] text-sm"
      >Descargar app para Android</button>
      <p className="text-xs text-gray-400 mt-2">{detalle}. La app se actualiza sola cuando publicamos una versión nueva.</p>
    </div>
  );
}
