import { format } from 'date-fns';
import { es } from 'date-fns/locale';
import { useMailStore } from '../../store/mailStore';
import { fechasQueNoCuadran } from '../../lib/fechaCorreo';

interface Props {
  msg: { folder: string; date: string | null; received_date?: string | null };
}

const FORMATO = "d 'de' MMMM 'de' yyyy, HH:mm";

/**
 * Aviso cuando la fecha que trae el correo no coincide con la hora en que llegó a nuestro
 * servidor (13/10/2026). La fecha del correo la pone el equipo del remitente y se puede
 * cambiar con el reloj de Windows; la de llegada no. Informa, no acusa: un reloj mal
 * puesto o un correo retenido en una cola también lo producen.
 */
export default function AvisoFechaRemitente({ msg }: Props) {
  const folders = useMailStore(s => s.folders);
  const fechas = fechasQueNoCuadran(msg, folders);
  if (!fechas) return null;
  return (
    <div
      role="note"
      className="mt-2 flex gap-2 items-start rounded border border-[#c7e0f4] bg-[#f3f9fd] dark:border-[#2b4a66] dark:bg-[#1a2a3a] px-3 py-2 text-[12px] text-[#323130] dark:text-[#e0e0e0]"
    >
      <svg className="w-4 h-4 flex-shrink-0 mt-[1px] text-[#0078d4]" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
        <circle cx="12" cy="12" r="9" /><path strokeLinecap="round" d="M12 7v5l3 2" />
      </svg>
      <span>
        La fecha que trae este correo (<b>{format(fechas.remitente, FORMATO, { locale: es })}</b>) no coincide con la
        hora en que llegó a nuestro servidor (<b>{format(fechas.llegada, FORMATO, { locale: es })}</b>). La fecha del
        correo la pone el equipo del remitente; la de llegada la registra el servidor y es la que vale.
      </span>
    </div>
  );
}
