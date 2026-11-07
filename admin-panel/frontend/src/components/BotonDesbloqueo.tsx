import { useEffect, useState } from "react";
import { api } from "../api/client";

// Bloqueo temporal de ingreso al webmail por intentos fallidos (10 en 15 minutos).
// La página pide una sola vez el estado de todos los buzones (useBloqueosAcceso) y cada
// fila muestra su estado y el botón «Desbloquear» (BotonDesbloqueo).
export interface EstadoBloqueo { intentos: number; bloqueado: boolean; segundos_restantes: number }

export function useBloqueosAcceso() {
  const [mapa, setMapa] = useState<Record<string, EstadoBloqueo>>({});
  const recargar = () => api.get<Record<string, EstadoBloqueo>>("/mailboxes/bloqueos/activos").then(setMapa).catch(() => setMapa({}));
  useEffect(() => {
    recargar();
    // Cada minuto: los bloqueos caducan solos y aparecen otros nuevos.
    const t = setInterval(recargar, 60000);
    return () => clearInterval(t);
  }, []);
  return { mapa, recargar };
}

export function BotonDesbloqueo({ username, estado, onHecho }: { username: string; estado?: EstadoBloqueo; onHecho: () => void }) {
  const [ocupado, setOcupado] = useState(false);
  if (!estado || estado.intentos <= 0) return null;
  const minutos = Math.max(1, Math.ceil(estado.segundos_restantes / 60));

  const desbloquear = async () => {
    const texto = estado.bloqueado
      ? `${username} está bloqueado por intentos fallidos de ingreso (le quedan ${minutos} min).\n\n¿Quitar el bloqueo ahora? Podrá volver a intentar al instante. Si no fue la persona, conviene cambiar la contraseña. Se registra en auditoría.`
      : `${username} tiene ${estado.intentos} intentos fallidos de ingreso (se bloquea al pasar de 10).\n\n¿Poner el contador en cero? Se registra en auditoría.`;
    if (!confirm(texto)) return;
    setOcupado(true);
    try {
      await api.post(`/mailboxes/${encodeURIComponent(username)}/desbloquear`);
      onHecho();
    } catch (e: any) {
      alert("No se pudo desbloquear: " + (e.message || "error desconocido"));
    }
    setOcupado(false);
  };

  return (
    <span className="inline-flex items-center gap-1 mr-1">
      <span
        title={estado.bloqueado
          ? `No puede entrar al webmail: ${estado.intentos} intentos fallidos. El bloqueo se quita solo en ${minutos} min.`
          : `${estado.intentos} intentos fallidos en los últimos 15 minutos. Con más de 10 se bloquea el ingreso.`}
        className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${estado.bloqueado ? "bg-red-50 text-ms-red" : "bg-yellow-50 text-yellow-700"}`}>
        {estado.bloqueado ? `Bloqueado · ${minutos} min` : `${estado.intentos} intentos`}
      </span>
      <button onClick={desbloquear} disabled={ocupado}
        title="Quita en el acto el bloqueo temporal de ingreso por intentos fallidos. Se registra en auditoría."
        className="text-ms-red hover:underline text-xs font-medium disabled:opacity-50">{ocupado ? "..." : "Desbloquear"}</button>
    </span>
  );
}
