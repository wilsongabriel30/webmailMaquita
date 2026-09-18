import { useEffect, useState } from 'react';

interface Manifiesto { versionName?: string; tamano?: number; fecha?: string; notas?: string; }

const RUTA_JSON = '/webmail/descargas/maquita-mail.json';
const RUTA_APK = '/webmail/descargas/maquita-mail.apk';

/** Botón «Descargar app para Android» (AM-11): solo aparece si el servidor tiene una versión publicada. */
export default function DescargaAppAndroid() {
  const [m, setM] = useState<Manifiesto | null>(null);

  useEffect(() => {
    let vivo = true;
    fetch(RUTA_JSON, { cache: 'no-store' })
      .then(r => (r.ok && (r.headers.get('content-type') || '').includes('json') ? r.json() : null))
      .then(j => { if (vivo && j && j.versionName) setM(j); })
      .catch(() => { /* sin versión publicada: no se muestra nada */ });
    return () => { vivo = false; };
  }, []);

  if (!m) return null;
  const mb = m.tamano ? ` · ${(m.tamano / 1048576).toFixed(1)} MB` : '';

  return (
    <div className="bg-white border rounded-lg p-4">
      <h4 className="font-medium mb-2">🤖 Android — aplicación Maquita Mail</h4>
      <p className="text-sm text-[#605e5c] mb-3">
        Instale la aplicación oficial: entra con su correo y su contraseña, avisa de los mensajes nuevos y se actualiza sola.
      </p>
      <a
        href={RUTA_APK}
        className="inline-block bg-[#0078d4] text-white px-4 py-2 rounded hover:bg-[#106ebe] text-sm"
      >Descargar app para Android</a>
      <p className="text-xs text-gray-400 mt-2">
        Versión {m.versionName}{mb}{m.fecha ? ` · ${m.fecha}` : ''}. Android pedirá permiso para instalar aplicaciones desde el navegador: es normal, la aplicación es de su propia organización.
      </p>
    </div>
  );
}
