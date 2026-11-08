import { useState } from 'react';
import { useNombreApp } from '../../lib/marca';

/** Acceso directo al correo web en el escritorio o el celular (opcional, 07/11/2026).
 *  Antes se ofrecía solo con un aviso en la parte inferior que salía cada cierto tiempo; ahora solo
 *  se instala si la persona lo pide aquí. Usa los ganchos que deja `InstallPrompt` en `window`. */
function yaInstalada(): boolean {
  return window.matchMedia('(display-mode: standalone)').matches
    || (window.navigator as Navigator & { standalone?: boolean }).standalone === true;
}

export default function AccesoDirectoWeb() {
  const nombre = useNombreApp();
  const [instalada] = useState(yaInstalada);
  const [ayuda, setAyuda] = useState(false);

  if (instalada) return null;

  const instalar = () => {
    if (window.__pwaInstallPrompt || /iPad|iPhone|iPod/.test(navigator.userAgent)) {
      window.__pwaInstallFn?.();
    } else {
      setAyuda(true);
    }
  };

  return (
    <div className="bg-white border rounded-lg p-4">
      <h4 className="font-medium mb-2">🌐 Acceso directo al correo web (opcional)</h4>
      <p className="text-sm text-[#605e5c] mb-3">
        Crea un icono de {nombre} en el escritorio o en la pantalla de inicio que abre este mismo correo web
        en su propia ventana. No hace falta si ya usa las aplicaciones de arriba.
      </p>
      <button
        type="button"
        onClick={instalar}
        className="inline-block border border-[#0078d4] text-[#0078d4] px-4 py-2 rounded hover:bg-[#f3f9fd] text-sm"
      >Crear acceso directo</button>
      {ayuda && (
        <p className="text-xs text-[#605e5c] mt-2">
          Este navegador no lo permite desde aquí: abra el menú del navegador (⋮) y elija «Instalar aplicación»
          o «Crear acceso directo».
        </p>
      )}
    </div>
  );
}
