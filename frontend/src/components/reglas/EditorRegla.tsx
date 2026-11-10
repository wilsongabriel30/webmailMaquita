import { useState } from 'react';
import { api } from '../../api/client';
import { accionVacia, condicionVacia, type Regla } from '../../lib/reglas/tipos';
import { FilaAccion } from './FilaAccion';
import { FilaCondicion } from './FilaCondicion';

/* Formulario de una regla: nombre, condiciones (todas/alguna), acciones y opciones. Sin guardar: eso
   lo hace quien lo contiene (ModalRegla). */

const claseSeccion = 'bg-white p-3 rounded border border-[#edebe9] space-y-2';
const claseAnadir = 'text-[13px] text-[#0078d4] hover:underline';

interface VistaPrevia { matching_count: number; sample_subjects: string[] }

export function EditorRegla({ regla, onCambio }: { regla: Regla; onCambio: (r: Regla) => void }) {
  const [previa, setPrevia] = useState<VistaPrevia | null>(null);
  const [previaCargando, setPreviaCargando] = useState(false);
  // La vista previa del servidor cuenta correos de la Bandeja de entrada por una condición de De/Para/Asunto.
  const condicionPrevia = regla.conditions.find(c => ['from', 'to', 'subject'].includes(c.field) && ['contains', 'is', 'matches'].includes(c.operator) && c.value.trim());

  const verPrevia = async () => {
    if (!condicionPrevia) return;
    setPreviaCargando(true);
    try {
      const r = await api.get<VistaPrevia>(`/sieve/filters/preview?field=${condicionPrevia.field}&operator=${condicionPrevia.operator}&value=${encodeURIComponent(condicionPrevia.value)}`);
      setPrevia(r);
    } catch { setPrevia(null); }
    finally { setPreviaCargando(false); }
  };

  const cambiarCondicion = (i: number, c: Regla['conditions'][number]) =>
    onCambio({ ...regla, conditions: regla.conditions.map((x, j) => (j === i ? c : x)) });
  const cambiarAccion = (i: number, a: Regla['actions'][number]) =>
    onCambio({ ...regla, actions: regla.actions.map((x, j) => (j === i ? a : x)) });

  return (
    <div className="space-y-3">
      <label className="block">
        <span className="text-xs font-semibold text-[#605e5c] uppercase tracking-wider">Nombre de la regla</span>
        <input value={regla.name} onChange={e => onCambio({ ...regla, name: e.target.value })} maxLength={80}
          className="mt-1 w-full px-3 py-2 border border-[#8a8886] rounded text-sm focus:border-[#0078d4] outline-none"
          placeholder="Ej.: Facturas de proveedores" />
      </label>

      <div className={claseSeccion}>
        <div className="flex flex-wrap items-center gap-2 text-sm text-[#323130]">
          <span className="text-xs font-semibold text-[#605e5c] uppercase tracking-wider">Condiciones</span>
          <span>· aplicar si se cumple</span>
          <select aria-label="Todas o alguna de las condiciones" value={regla.match}
            onChange={e => onCambio({ ...regla, match: e.target.value as Regla['match'] })}
            className="px-2 py-1 border border-[#8a8886] rounded text-sm">
            <option value="allof">todas las condiciones</option>
            <option value="anyof">alguna de las condiciones</option>
          </select>
        </div>
        {regla.conditions.map((c, i) => (
          <FilaCondicion key={i} condicion={c} autoFocus={i === 0 && !c.value}
            onCambio={x => cambiarCondicion(i, x)}
            onQuitar={() => onCambio({ ...regla, conditions: regla.conditions.filter((_, j) => j !== i) })}
            puedeQuitar={regla.conditions.length > 1} />
        ))}
        <div className="flex flex-wrap items-center gap-4">
          {regla.conditions.length < 10 && (
            <button type="button" className={claseAnadir} onClick={() => onCambio({ ...regla, conditions: [...regla.conditions, condicionVacia()] })}>
              + Añadir condición
            </button>
          )}
          <button type="button" className={claseAnadir} onClick={verPrevia} disabled={!condicionPrevia || previaCargando}
            title={condicionPrevia ? 'Cuántos correos de la Bandeja de entrada cumplen la primera condición de De, Para o Asunto' : 'Disponible con una condición de De, Para o Asunto'}>
            {previaCargando ? 'Comprobando…' : 'Ver cuántos correos coinciden'}
          </button>
        </div>
        {previa && (
          <div className="p-2 bg-[#deecf9] rounded text-xs text-[#323130]">
            <b>{previa.matching_count}</b> correo{previa.matching_count !== 1 ? 's' : ''} de la Bandeja de entrada cumple{previa.matching_count !== 1 ? 'n' : ''} «{condicionPrevia?.value}»
            {previa.sample_subjects.length > 0 && (
              <ul className="mt-1 space-y-0.5 text-[#605e5c]">{previa.sample_subjects.map((s, i) => <li key={i} className="truncate">- {s}</li>)}</ul>
            )}
          </div>
        )}
      </div>

      <div className={claseSeccion}>
        <div className="text-xs font-semibold text-[#605e5c] uppercase tracking-wider">Acciones</div>
        {regla.actions.map((a, i) => (
          <FilaAccion key={i} accion={a} onCambio={x => cambiarAccion(i, x)}
            onQuitar={() => onCambio({ ...regla, actions: regla.actions.filter((_, j) => j !== i) })}
            puedeQuitar={regla.actions.length > 1} />
        ))}
        {regla.actions.length < 5 && (
          <button type="button" className={claseAnadir} onClick={() => onCambio({ ...regla, actions: [...regla.actions, accionVacia()] })}>
            + Añadir acción
          </button>
        )}
      </div>

      <div className="flex flex-wrap gap-x-6 gap-y-2 text-sm text-[#323130]">
        <label className="flex items-center gap-2">
          <input type="checkbox" checked={regla.stop} onChange={e => onCambio({ ...regla, stop: e.target.checked })} />
          No aplicar más reglas a este correo
        </label>
        <label className="flex items-center gap-2">
          <input type="checkbox" checked={regla.enabled} onChange={e => onCambio({ ...regla, enabled: e.target.checked })} />
          Regla activa
        </label>
      </div>
      <p className="text-xs text-[#605e5c]">
        Las reglas se aplican a los correos que lleguen de ahora en adelante, en el orden en que aparecen en Ajustes › Reglas de correo;
        con la casilla de abajo también a los que ya están en la Bandeja de entrada.
        «Coincide con el patrón» admite * y ?; la expresión regular sigue la sintaxis POSIX extendida.
      </p>
    </div>
  );
}
