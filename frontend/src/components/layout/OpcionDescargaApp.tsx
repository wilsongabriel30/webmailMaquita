import { textoTamano, urlApk, useManifiestoApp } from '../../lib/appAndroid';

/** Opción del menú del perfil: descarga de la app Android (solo con versión publicada y fuera de la app). */
export default function OpcionDescargaApp({ alPulsar }: { alPulsar?: () => void }) {
  const m = useManifiestoApp();
  if (!m) return null;
  return (
    <button
      onClick={() => { alPulsar?.(); window.open(urlApk(), '_blank'); }}
      title={`Versión ${m.versionName}${m.tamano ? ' · ' + textoTamano(m) : ''}`}
      className="w-full text-left px-4 py-2 text-[13px] text-[#323130] hover:bg-[#f3f2f1] flex items-center gap-2">
      <svg className="w-4 h-4 text-[#605e5c]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 4v12m0 0l-4-4m4 4l4-4M5 20h14" />
      </svg>
      <span>Descargar app para Android <span className="text-[11px] text-[#605e5c]">({m.versionName}{m.tamano ? ' · ' + textoTamano(m) : ''})</span></span>
    </button>
  );
}
