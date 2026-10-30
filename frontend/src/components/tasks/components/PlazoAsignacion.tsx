// «Tiempo de realización» del recuadro «Asignar tarea a:»: Hoy, Mañana, En 3 días, La próxima semana o una fecha.
// El plazo queda como fecha de vencimiento de la tarea (así le salen los avisos de «Vence hoy» a quien la recibe).
import { COLORS } from '../types';

function enDias(n: number): string {
  const d = new Date();
  d.setDate(d.getDate() + n);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

/** Próximo lunes (como «La próxima semana» de To Do). */
function proximaSemana(): string {
  const dia = new Date().getDay();
  return enDias(dia === 0 ? 1 : 8 - dia);
}

const chip = (activo: boolean) => ({
  fontSize: 12, padding: '4px 10px', borderRadius: 12, cursor: 'pointer', fontFamily: 'inherit',
  border: `1px solid ${activo ? COLORS.primary : COLORS.border}`,
  background: activo ? COLORS.primary : 'white', color: activo ? 'white' : COLORS.text,
});

export function PlazoAsignacion({ valor, onCambiar }: { valor: string; onCambiar: (fecha: string) => void }) {
  const opciones = [
    { label: 'Hoy', fecha: enDias(0) },
    { label: 'Mañana', fecha: enDias(1) },
    { label: 'En 3 días', fecha: enDias(3) },
    { label: 'La próxima semana', fecha: proximaSemana() },
  ];
  return (
    <div role="group" aria-label="Tiempo de realización" style={{ fontSize: 12, color: COLORS.secondary }}>
      Tiempo de realización (plazo)
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginTop: 4, alignItems: 'center' }}>
        {opciones.map(o => (
          <button key={o.label} type="button" aria-pressed={valor === o.fecha} style={chip(valor === o.fecha)}
            onClick={() => onCambiar(valor === o.fecha ? '' : o.fecha)}>
            {o.label}
          </button>
        ))}
        <input type="date" aria-label="Elegir la fecha del plazo" value={valor} min={enDias(0)}
          onChange={e => onCambiar(e.target.value)}
          style={{ fontSize: 12, border: `1px solid ${COLORS.border}`, borderRadius: 4, padding: '3px 6px', fontFamily: 'inherit' }} />
      </div>
    </div>
  );
}
