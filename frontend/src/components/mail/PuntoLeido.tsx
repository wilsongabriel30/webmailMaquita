/**
 * Puntito de no leído clicable (07/11/2026, como Outlook).
 * Azul = sin leer: un clic lo marca como leído. Ya leído: al pasar el ratón por la fila aparece
 * un círculo vacío y un clic lo vuelve a marcar como no leído. Es un atajo más: los iconos de la
 * fila y el menú siguen igual.
 */
export function PuntoLeido({ noLeido, esSpam, motivoSpam, onAlternar }: {
  noLeido: boolean; esSpam?: boolean; motivoSpam?: string;
  onAlternar: (e: React.MouseEvent) => void;
}) {
  const titulo = esSpam && motivoSpam ? motivoSpam : noLeido ? 'Marcar como leído' : 'Marcar como no leído';
  return (
    <button type="button" title={titulo} aria-label={noLeido ? 'Marcar como leído' : 'Marcar como no leído'}
      onClick={e => { e.stopPropagation(); onAlternar(e); }}
      onDoubleClick={e => e.stopPropagation()}
      className="-ml-[5px] w-[16px] h-[16px] shrink-0 flex items-center justify-center rounded-full bg-transparent border-0 p-0 cursor-pointer hover:bg-[#deecf9]">
      <span className={`w-[8px] h-[8px] rounded-full ${
        esSpam ? 'bg-[#ca5010]'
          : noLeido ? 'bg-[#0078d4]'
          : 'border-[1.5px] border-transparent group-hover:border-[#0078d4]'
      }`} />
    </button>
  );
}
