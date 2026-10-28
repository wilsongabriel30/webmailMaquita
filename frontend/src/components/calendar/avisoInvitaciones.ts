// Avisos de las invitaciones del calendario que no llegan.
// El servidor responde al instante con lo que no pudo ni siquiera enviar («fallido»). Lo que sí salió puede
// rechazarlo el destino segundos después (dirección inexistente, bloqueo, buzón lleno): por eso se consulta
// el estado de entrega unas veces y se avisa, con un aviso que no se cierra solo, de cada invitación que no llegó.
import { api } from "../../api/client";
import { showToast } from "../common/Toast";

export interface ResultadoInvitacion {
  email: string;
  estado: "aceptado" | "fallido" | "entregado" | "rechazado" | "en_espera";
  message_id?: string;
  detalle?: string;
  dsn?: string | null;
}

export interface RespuestaInvitaciones {
  sent: number;
  resultados?: ResultadoInvitacion[];
}

// Segundos tras el envío en que se consulta el estado (los rechazos suelen llegar en 1–5 s).
const CONSULTAS_S = [4, 10, 25, 60];

function avisar(titulo: string, fallos: ResultadoInvitacion[]) {
  if (!fallos.length) return;
  const lineas = fallos.map((f) => `${f.email}: ${f.detalle || "no se pudo entregar"}`);
  showToast(`${titulo} ${lineas.join(" · ")}`, undefined, { fijo: true });
}

export function avisarFalloGeneralInvitaciones() {
  showToast("El evento se guardó, pero no se pudieron enviar las invitaciones. Ábrelo y vuelve a guardarlo para reintentar.",
    undefined, { fijo: true });
}

export function avisarResultadoInvitaciones(res: RespuestaInvitaciones) {
  const resultados = res.resultados || [];
  const fallidos = resultados.filter((r) => r.estado === "fallido");
  avisar(fallidos.length === 1 ? "No se pudo enviar la invitación a" : "No se pudieron enviar las invitaciones a", fallidos);

  const pendientes = new Map<string, string>(); // message_id → email
  for (const r of resultados) if (r.estado === "aceptado" && r.message_id) pendientes.set(r.message_id, r.email);
  if (!pendientes.size) return;

  const enEspera = new Map<string, ResultadoInvitacion>();
  let consulta = 0;
  const siguiente = () => {
    if (consulta >= CONSULTAS_S.length || !pendientes.size) {
      // Al terminar, lo que el destino aún no recibió se avisa una vez: el servidor seguirá intentando.
      const sinRecibir = [...enEspera.values()].filter((r) => r.message_id && pendientes.has(r.message_id));
      avisar("Invitación todavía sin entregar (se seguirá intentando):", sinRecibir);
      return;
    }
    const espera = (CONSULTAS_S[consulta] - (consulta ? CONSULTAS_S[consulta - 1] : 0)) * 1000;
    consulta++;
    window.setTimeout(async () => {
      try {
        const ids = [...pendientes.keys()].join(",");
        const r = await api.get<{ resultados: ResultadoInvitacion[] }>(
          "/calendar/invitaciones/estado?ids=" + encodeURIComponent(ids));
        const rechazados: ResultadoInvitacion[] = [];
        for (const e of r?.resultados || []) {
          if (!e.message_id || !pendientes.has(e.message_id)) continue;
          if (e.estado === "entregado") pendientes.delete(e.message_id);
          else if (e.estado === "rechazado") { pendientes.delete(e.message_id); rechazados.push(e); }
          else if (e.estado === "en_espera") enEspera.set(e.message_id, e);
        }
        avisar(rechazados.length === 1 ? "La invitación no llegó a" : "Las invitaciones no llegaron a", rechazados);
      } catch {
        /* sin conexión: se vuelve a intentar en la siguiente consulta */
      }
      siguiente();
    }, espera);
  };
  siguiente();
}
