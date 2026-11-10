import { ETIQUETA_CAMPO, ETIQUETA_OPERADOR, operadoresDe, type CampoCondicion, type CondicionRegla, type OperadorCondicion } from '../../lib/reglas/tipos';

/* Una condición de la regla: campo, operador y valor (más el nombre del encabezado si aplica). */

const CAMPOS = Object.keys(ETIQUETA_CAMPO) as CampoCondicion[];
const claseControl = 'px-2 py-2 border border-[#8a8886] rounded text-sm focus:border-[#0078d4] outline-none';

export function FilaCondicion({ condicion, onCambio, onQuitar, puedeQuitar, autoFocus }: {
  condicion: CondicionRegla;
  onCambio: (c: CondicionRegla) => void;
  onQuitar: () => void;
  puedeQuitar: boolean;
  autoFocus?: boolean;
}) {
  const operadores = operadoresDe(condicion.field);
  const sinValor = condicion.operator === 'exists' || condicion.operator === 'not_exists';

  const cambiarCampo = (field: CampoCondicion) => {
    const validos = operadoresDe(field);
    const operator = validos.includes(condicion.operator) ? condicion.operator : validos[0];
    onCambio({ ...condicion, field, operator, value: field === 'size' && !/^\d+$/.test(condicion.value) ? '' : condicion.value });
  };

  return (
    <div className="flex flex-wrap items-center gap-2" role="group" aria-label="Condición">
      <select aria-label="Campo" value={condicion.field} onChange={e => cambiarCampo(e.target.value as CampoCondicion)} className={claseControl}>
        {CAMPOS.map(c => <option key={c} value={c}>{ETIQUETA_CAMPO[c]}</option>)}
      </select>
      {condicion.field === 'header' && (
        <input aria-label="Nombre del encabezado" value={condicion.header || ''} placeholder="X-Mailer, Reply-To…"
          onChange={e => onCambio({ ...condicion, header: e.target.value })} className={`${claseControl} w-40`} />
      )}
      <select aria-label="Operador" value={condicion.operator} onChange={e => onCambio({ ...condicion, operator: e.target.value as OperadorCondicion })} className={claseControl}>
        {operadores.map(o => <option key={o} value={o}>{ETIQUETA_OPERADOR[o]}</option>)}
      </select>
      {!sinValor && (
        <input aria-label="Valor" value={condicion.value} autoFocus={autoFocus}
          inputMode={condicion.field === 'size' ? 'numeric' : undefined}
          placeholder={condicion.field === 'size' ? 'KB, p. ej. 5000' : condicion.field === 'from' ? 'nombre@dominio.org o dominio.org' : 'texto…'}
          onChange={e => onCambio({ ...condicion, value: e.target.value })} className={`${claseControl} flex-1 min-w-[180px]`} />
      )}
      <button type="button" onClick={onQuitar} disabled={!puedeQuitar} aria-label="Quitar condición" title="Quitar condición"
        className="w-8 h-8 flex items-center justify-center rounded text-[#605e5c] hover:bg-[#edebe9] hover:text-[#a4262c] disabled:opacity-30">
        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" /></svg>
      </button>
    </div>
  );
}
