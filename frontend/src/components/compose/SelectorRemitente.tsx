// Selector «De» del redactor: la propia cuenta y las delegadas con permiso de envío.
// Solo se muestra cuando hay más de una opción.
// Con una cuenta asignada activa (barra de cuentas) el remitente es esa cuenta, fijo: el correo
// sale desde ella y la copia queda en sus Enviados (backend: mail/services/cuenta_activa.py).
import { useMailStore } from '../../store/mailStore';
import { colorDeCuenta, cuentaActiva } from '../../lib/cuentaActiva';

export function SelectorRemitente({ valor, onChange }: { valor: string; onChange: (email: string) => void }) {
  const cuentas = useMailStore(s => s.cuentas);
  const activa = cuentaActiva();
  if (activa) {
    const c = cuentas.find(x => x.email.toLowerCase() === activa);
    return (
      <div className="flex items-center gap-2 px-4 py-[6px] border-b border-[#edebe9] text-[13px]" data-prueba="remitente-fijo">
        <span className="w-[42px] text-[#605e5c]">De</span>
        <span className="flex-1 text-[#323130] truncate" title="Este correo sale desde la cuenta asignada que tienes abierta. La copia queda en sus Enviados.">
          <span className="inline-block w-2 h-2 rounded-full mr-1.5 align-middle" style={{ backgroundColor: colorDeCuenta(activa) }} />
          {c?.nombre ? `${c.nombre} <${activa}>` : activa}
          <span className="text-[#605e5c]"> (cuenta asignada)</span>
          {c && !c.puede_enviar && (
            <span className="block text-[12px] text-[#a4262c] font-semibold" data-prueba="solo-lectura">
              Esta cuenta está asignada solo para lectura: no puedes enviar desde ella.
            </span>
          )}
        </span>
      </div>
    );
  }
  const opciones = cuentas.filter(c => c.propia || c.puede_enviar);
  if (opciones.length < 2) return null;
  const propia = opciones.find(c => c.propia);
  return (
    <div className="flex items-center gap-2 px-4 py-[6px] border-b border-[#edebe9] text-[13px]">
      <span className="w-[42px] text-[#605e5c]">De</span>
      <select value={valor || propia?.email || ''} onChange={e => onChange(e.target.value)}
        title="Cuenta desde la que sale este correo. La copia queda en los Enviados de esa cuenta."
        className="flex-1 bg-transparent outline-none text-[#323130] cursor-pointer">
        {opciones.map(c => (
          <option key={c.email} value={c.email}>
            {c.nombre ? `${c.nombre} <${c.email}>` : c.email}{c.propia ? ' (mi cuenta)' : ''}
          </option>
        ))}
      </select>
    </div>
  );
}
