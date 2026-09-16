/**
 * Mensaje amable cuando una búsqueda no encuentra nada: saluda por el nombre de la persona,
 * dice qué se buscó y sugiere cómo afinar la búsqueda (ámbito, operadores, adjuntos).
 */
import { useMailStore } from '../../store/mailStore';
import { useAuthStore } from '../../store/authStore';
import { aplicarBusqueda, cambiarAmbito } from '../../lib/busquedaGlobal';

interface Props { consulta: string; enTodo: boolean; carpeta: string; }

function primerNombre(): string {
  const st = useMailStore.getState();
  const activa = st.cuentas[0];  // la primera es la cuenta principal
  const auth = useAuthStore.getState() as unknown as { user?: { display_name?: string; name?: string; username?: string } | null; username?: string };
  const nombre = activa?.nombre || auth.user?.display_name || auth.user?.name || '';
  if (nombre) return nombre.trim().split(/\s+/)[0];
  const correo = activa?.email || auth.user?.username || auth.username || '';
  const local = correo.split('@')[0] || '';
  return local ? local.charAt(0).toUpperCase() + local.slice(1) : '';
}

export function SinResultados({ consulta, enTodo, carpeta }: Props) {
  const nombre = primerNombre();
  const saludo = nombre ? `Hola ${nombre}, ` : 'Hola, ';
  const tieneOperador = consulta.includes(':');
  return (
    <div className="max-w-[360px] text-center px-4">
      <p className="text-[13px] text-[#323130]">
        {saludo}no encontramos ningún correo con «{consulta}»{enTodo ? ' en todo tu correo' : ` en ${carpeta}`}.
      </p>
      <p className="text-[12px] text-[#605e5c] mt-2">Sugerencias para afinar la búsqueda:</p>
      <ul className="text-[12px] text-[#605e5c] text-left mt-1 space-y-1 list-disc pl-5">
        {!enTodo && (
          <li>
            <button type="button" className="text-[#0078d4] hover:underline" onClick={() => cambiarAmbito(true)}>
              Buscar en todas las carpetas
            </button> (enviados, papelera y carpetas propias).
          </li>
        )}
        <li>Revisa la ortografía o usa una palabra más corta (con 3 letras basta).</li>
        {!tieneOperador && (
          <li>Acota con operadores: <code>de:nombre</code>, <code>asunto:palabra</code>, <code>despues:2026-01-01</code>, <code>semana</code>.</li>
        )}
        <li>¿Buscas un archivo? Prueba <code>adjunto:factura</code> o <code>adjunto:.pdf</code>.</li>
        <li>Para buscar dentro del texto de los mensajes usa <code>contenido:palabra</code>.</li>
      </ul>
      <button type="button" onClick={() => aplicarBusqueda('')} className="text-[11px] mt-3 text-[#0078d4] hover:underline">
        Limpiar la búsqueda
      </button>
    </div>
  );
}
