// Selector «De» del redactor: la propia cuenta y las delegadas con permiso de envío.
// Solo se muestra cuando hay más de una opción.
import { useMailStore } from '../../store/mailStore';

export function SelectorRemitente({ valor, onChange }: { valor: string; onChange: (email: string) => void }) {
  const cuentas = useMailStore(s => s.cuentas);
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
