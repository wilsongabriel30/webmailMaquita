import { ACCIONES_CON_CARPETA, ACCIONES_CON_CORREO, ETIQUETA_ACCION, type AccionRegla, type TipoAccion } from '../../lib/reglas/tipos';
import { SelectorCarpeta } from './SelectorCarpeta';

/* Una acción de la regla: tipo y, según el tipo, carpeta, bandera o dirección. */

const TIPOS = Object.keys(ETIQUETA_ACCION) as TipoAccion[];
const claseControl = 'px-2 py-2 border border-[#8a8886] rounded text-sm focus:border-[#0078d4] outline-none';

export function FilaAccion({ accion, onCambio, onQuitar, puedeQuitar }: {
  accion: AccionRegla;
  onCambio: (a: AccionRegla) => void;
  onQuitar: () => void;
  puedeQuitar: boolean;
}) {
  const cambiarTipo = (type: TipoAccion) => {
    const conservaCarpeta = ACCIONES_CON_CARPETA.includes(type) && ACCIONES_CON_CARPETA.includes(accion.type);
    const conservaCorreo = ACCIONES_CON_CORREO.includes(type) && ACCIONES_CON_CORREO.includes(accion.type);
    onCambio({ type, value: conservaCarpeta || conservaCorreo ? accion.value : type === 'flag' ? '\\Flagged' : '' });
  };
  return (
    <div className="flex flex-wrap items-center gap-2" role="group" aria-label="Acción">
      <select aria-label="Acción" value={accion.type} onChange={e => cambiarTipo(e.target.value as TipoAccion)} className={claseControl}>
        {TIPOS.map(t => <option key={t} value={t}>{ETIQUETA_ACCION[t]}</option>)}
      </select>
      {ACCIONES_CON_CARPETA.includes(accion.type) && (
        <SelectorCarpeta valor={accion.value || ''} onCambio={v => onCambio({ ...accion, value: v })} />
      )}
      {ACCIONES_CON_CORREO.includes(accion.type) && (
        <input type="email" aria-label="Dirección de reenvío" value={accion.value || ''} placeholder="persona@dominio.org"
          onChange={e => onCambio({ ...accion, value: e.target.value })} className={`${claseControl} min-w-[220px]`} />
      )}
      {accion.type === 'delete' && <span className="text-xs text-[#a4262c]">El correo se descarta sin pasar por la Papelera.</span>}
      <button type="button" onClick={onQuitar} disabled={!puedeQuitar} aria-label="Quitar acción" title="Quitar acción"
        className="w-8 h-8 flex items-center justify-center rounded text-[#605e5c] hover:bg-[#edebe9] hover:text-[#a4262c] disabled:opacity-30">
        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" /></svg>
      </button>
    </div>
  );
}
