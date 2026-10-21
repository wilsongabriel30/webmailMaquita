import { useEffect, useState } from "react";
import { api } from "../../api/client";

interface Comprobacion { hora: string; ok: boolean; codigo: number | null; ms: number | null; dias_certificado: number | null; motivo: string | null }
interface Datos {
  https: boolean;
  caido: boolean;
  caido_desde: string | null;
  ultima: Comprobacion | null;
  porcentaje: number | null;
  historial: Comprobacion[];
  avisos: { dia: string; hora: string; asunto: string; enviado: boolean }[];
  destinatarios: string[];
}

/* Comprobaciones de cada 5 minutos (código, tiempo y certificado) de las últimas 24 horas, y avisos enviados. */
export function DisponibilidadPestana({ dominio }: { dominio: string }) {
  const [datos, setDatos] = useState<Datos | null>(null);
  const [error, setError] = useState("");
  useEffect(() => { api.get<Datos>(`/sitios/${dominio}/disponibilidad`).then(setDatos).catch((e) => setError(e.message)); }, [dominio]);

  if (error) return <p className="text-sm text-ms-red">{error}</p>;
  if (!datos) return <p className="text-sm text-ms-gray-60">Cargando…</p>;
  const u = datos.ultima;
  return (
    <div className="space-y-3">
      {!u && <p className="text-sm text-ms-gray-60">Todavía no hay comprobaciones: la primera se hace en menos de 5 minutos.</p>}
      {u && (
        <div className="flex flex-wrap gap-4 items-center text-sm">
          <span className={`px-2 py-0.5 rounded text-xs font-medium ${datos.caido ? "bg-red-50 text-ms-red" : u.ok ? "bg-green-50 text-ms-green" : "bg-yellow-50 text-ms-gray-130"}`}>
            {datos.caido ? `Sin servicio desde ${datos.caido_desde}` : u.ok ? "Responde" : "Falló la última comprobación"}
          </span>
          <span>Última: {u.hora} · {u.codigo ?? "sin respuesta"} · {u.ms} ms</span>
          {datos.https && u.dias_certificado != null && <span className={u.dias_certificado < 10 ? "text-ms-red" : ""}>Certificado: vence en {u.dias_certificado} días</span>}
          {!datos.https && <span className="text-ms-gray-60">Sin HTTPS: se comprueba por HTTP.</span>}
          {datos.porcentaje != null && <span>Disponible el {datos.porcentaje} % de las últimas 24 h</span>}
        </div>
      )}
      {datos.historial.length > 0 && (
        <div className="flex gap-px h-6" aria-label="Historial de comprobaciones">
          {datos.historial.map((h, i) => <div key={i} title={`${h.hora}: ${h.ok ? `${h.codigo}, ${h.ms} ms` : h.motivo}`} className={`flex-1 ${h.ok ? "bg-ms-green/70" : "bg-ms-red"}`} />)}
        </div>
      )}
      {u && !u.ok && u.motivo && <p className="text-xs text-ms-red">Motivo: {u.motivo}</p>}
      <div className="text-xs text-ms-gray-90">
        <b>Avisos por correo</b> (tras 2 fallos seguidos y al volver; como mucho 6 al día) a: {datos.destinatarios.join(", ")}
        {datos.avisos.length > 0 && (
          <ul className="list-disc ml-4 mt-1">{datos.avisos.map((a, i) => <li key={i}>{a.dia} {a.hora} — {a.asunto}{a.enviado ? "" : " (no se pudo enviar)"}</li>)}</ul>
        )}
      </div>
      <p className="text-[11px] text-ms-gray-60">La comprobación se hace desde este mismo servidor con el nombre del sitio: revisa nginx, PHP, la aplicación y el certificado, sin depender del DNS. Un error 5xx, un certificado no válido o la falta de respuesta en 15 s cuentan como fallo.</p>
    </div>
  );
}
