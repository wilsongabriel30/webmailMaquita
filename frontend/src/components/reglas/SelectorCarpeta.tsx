import { useMemo } from 'react';
import { getFolderDisplayName } from '../../folders';
import { construirArbolCarpetas, type NodoCarpeta } from '../../lib/arbolCarpetas';
import { useMailStore } from '../../store/mailStore';

/* Lista desplegable de carpetas con sangría por nivel («Territorios › Napo › WWF»). */

function aplanar(nodos: NodoCarpeta[], salida: NodoCarpeta[] = []): NodoCarpeta[] {
  for (const n of nodos) { salida.push(n); aplanar(n.hijas, salida); }
  return salida;
}

export function SelectorCarpeta({ valor, onCambio, id, excluir = [] }: {
  valor: string;
  onCambio: (carpeta: string) => void;
  id?: string;
  excluir?: string[];
}) {
  const carpetas = useMailStore(s => s.folders);
  const opciones = useMemo(() => aplanar(construirArbolCarpetas(carpetas)).filter(n => !excluir.includes(n.nombre)), [carpetas, excluir]);
  const conocida = !valor || opciones.some(o => o.nombre === valor);
  return (
    <select id={id} value={valor} onChange={e => onCambio(e.target.value)} aria-label="Carpeta de destino"
      className="px-2 py-2 border border-[#8a8886] rounded text-sm min-w-[200px] max-w-full focus:border-[#0078d4] outline-none">
      <option value="">-- Elegir carpeta --</option>
      {!conocida && <option value={valor}>{getFolderDisplayName(valor)} (no existe aún)</option>}
      {opciones.map(o => (
        <option key={o.nombre} value={o.nombre}>
          {'  '.repeat(o.nivel)}{o.nivel > 0 ? '› ' : ''}{getFolderDisplayName(o.nombre)}
        </option>
      ))}
    </select>
  );
}
