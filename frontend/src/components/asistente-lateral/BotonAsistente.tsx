/** Botón de la barra superior que abre y cierra el panel lateral del asistente. */
import { useAsistenteStore } from './asistenteStore';
import { IconoAsistente } from './IconoAsistente';

export function BotonAsistente() {
  const abierto = useAsistenteStore((s) => s.abierto);
  const alternar = useAsistenteStore((s) => s.alternar);
  return (
    <button type="button" onClick={alternar} aria-pressed={abierto}
      title={abierto ? 'Cerrar el asistente' : 'Asistente: resume, responde y pregúntale a tu correo'}
      className={`h-8 px-2 rounded flex items-center gap-1.5 text-white/90 hover:bg-white/15 transition-colors ${abierto ? 'bg-white/20' : ''}`}>
      <IconoAsistente />
      <span className="text-[13px] max-md:hidden">Asistente</span>
    </button>
  );
}
