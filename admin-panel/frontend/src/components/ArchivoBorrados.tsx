/**
 * Papelera de recuperación: el correo que ya no está ni en la papelera del usuario.
 *
 * La papelera de arriba solo ve lo que el usuario aún tiene en su carpeta de eliminados. Cuando
 * alguien la vacía, esos correos desaparecen de su buzón, y es justo entonces cuando llega la
 * petición de soporte. Dovecot guarda una copia de todo lo borrado en una carpeta oculta del
 * propio buzón, y esto permite buscarla y devolverla sin entrar por SSH.
 *
 * Devolver un correo lo COPIA: la copia de seguridad se queda donde está, así que se puede
 * recuperar otra vez si hace falta. Queda registrado en la auditoría.
 */
import { useState } from "react";
import { api } from "../api/client";

interface Archivado {
  uid: string;
  fecha?: string;
  de?: string;
  asunto?: string;
}

interface Detalle {
  de?: string;
  para?: string;
  fecha?: string;
  asunto?: string;
  cuerpo?: string;
}

export function ArchivoBorrados({ username }: { username: string }) {
  const [texto, setTexto] = useState("");
  const [mensajes, setMensajes] = useState<Archivado[]>([]);
  const [cargando, setCargando] = useState(false);
  const [buscado, setBuscado] = useState(false);
  const [detalle, setDetalle] = useState<Detalle | null>(null);
  const [viendo, setViendo] = useState<string | null>(null);

  const buscar = () => {
    if (!username) return;
    setCargando(true);
    setDetalle(null);
    api
      .get(`/recovery/archivados/${username}?texto=${encodeURIComponent(texto)}`)
      .then((d: any) => setMensajes(d.mensajes || []))
      .catch(() => setMensajes([]))
      .finally(() => {
        setCargando(false);
        setBuscado(true);
      });
  };

  const ver = (uid: string) => {
    setViendo(uid);
    setDetalle(null);
    api
      .get(`/recovery/archivados/${username}/mensaje/${uid}`)
      .then((d: any) => setDetalle(d))
      .catch(() => setViendo(null));
  };

  const devolver = async (m: Archivado) => {
    const ok = confirm(
      `¿Devolver este correo a la bandeja de entrada de ${username}?\n\n` +
        `${m.asunto || "(sin asunto)"}\n\n` +
        `La copia de seguridad se conserva. Queda registrado en la auditoría.`,
    );
    if (!ok) return;
    try {
      await api.post("/recovery/archivados/restaurar", { buzon: username, uid: m.uid, destino: "INBOX" });
      alert("Correo devuelto a la bandeja de entrada.");
    } catch {
      alert("No se pudo devolver el correo. Inténtelo de nuevo o revise el registro.");
    }
  };

  return (
    <div className="space-y-3 pt-2">
      <div className="border-t border-ms-gray-30 pt-5">
        <h2 className="text-base font-semibold text-ms-gray-130">
          Papelera de recuperación
        </h2>
        <p className="text-xs text-ms-gray-60 mt-1 max-w-3xl">
          Aquí está el correo que ya <strong>no está ni en la papelera</strong>: lo que se borró del
          todo o se perdió al vaciar una carpeta. Devolver un correo lo copia a su bandeja; la copia
          de seguridad se conserva por si hace falta otra vez.
        </p>
      </div>

      <div className="flex gap-2">
        <input
          value={texto}
          onChange={(e) => setTexto(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && buscar()}
          placeholder="Asunto o remitente (vacío = todo lo borrado)"
          title="Busca por asunto o por remitente, que es como se suele recordar un correo."
          className="flex-1 px-3 py-2 border border-ms-gray-40 rounded text-sm focus:outline-none focus:border-ms-blue focus:ring-1 focus:ring-ms-blue"
        />
        <button
          onClick={buscar}
          disabled={cargando || !username}
          title={username ? "Busca en el correo borrado de este buzón. Solo lectura." : "Escriba antes el buzón del usuario."}
          className="px-5 py-2 bg-ms-blue text-white rounded text-sm hover:bg-ms-blue-dark disabled:opacity-50"
        >
          {cargando ? "Buscando..." : "Buscar borrados"}
        </button>
      </div>

      {mensajes.length > 0 && (
        <div className="bg-white rounded border border-ms-gray-30 overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-ms-gray-20 border-b border-ms-gray-30">
              <tr>
                <th className="text-left px-4 py-2.5 font-medium text-ms-gray-90 text-xs">Fecha</th>
                <th className="text-left px-4 py-2.5 font-medium text-ms-gray-90 text-xs">De</th>
                <th className="text-left px-4 py-2.5 font-medium text-ms-gray-90 text-xs">Asunto</th>
                <th className="text-right px-4 py-2.5 font-medium text-ms-gray-90 text-xs">Acción</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-ms-gray-30">
              {mensajes.map((m) => (
                <tr key={m.uid} className={`hover:bg-ms-blue-lighter/50 ${viendo === m.uid ? "bg-ms-blue-lighter" : ""}`}>
                  <td className="px-4 py-2.5 text-xs text-ms-gray-60 whitespace-nowrap">{m.fecha || "-"}</td>
                  <td className="px-4 py-2.5 text-xs text-ms-gray-130 truncate max-w-[220px]">{m.de || "-"}</td>
                  <td className="px-4 py-2.5 text-xs text-ms-gray-130 truncate max-w-[320px]">{m.asunto || "(sin asunto)"}</td>
                  <td className="px-4 py-2.5 text-right whitespace-nowrap">
                    <button
                      onClick={() => ver(m.uid)}
                      title="Ver el correo entero antes de devolverlo, para confirmar que es el que piden."
                      className="px-3 py-1 border border-ms-gray-40 rounded text-xs text-ms-gray-130 hover:bg-ms-gray-20 mr-2"
                    >
                      Ver
                    </button>
                    <button
                      onClick={() => devolver(m)}
                      title="Copia este correo a la bandeja de entrada del usuario. La copia de seguridad se conserva. Se registra en auditoría."
                      className="px-3 py-1 bg-ms-green text-white rounded text-xs hover:bg-green-700"
                    >
                      Devolver
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {detalle && (
        <div className="bg-white rounded border border-ms-gray-30 p-4 space-y-1">
          <div className="flex justify-between items-start">
            <h3 className="text-sm font-semibold text-ms-gray-130">{detalle.asunto || "(sin asunto)"}</h3>
            <button onClick={() => { setDetalle(null); setViendo(null); }} className="text-xs text-ms-gray-60 hover:text-ms-gray-130">
              Cerrar
            </button>
          </div>
          <p className="text-xs text-ms-gray-60">De: {detalle.de || "-"}</p>
          <p className="text-xs text-ms-gray-60">Para: {detalle.para || "-"}</p>
          <p className="text-xs text-ms-gray-60">Fecha: {detalle.fecha || "-"}</p>
          <pre className="text-xs text-ms-gray-130 whitespace-pre-wrap bg-ms-gray-20 rounded p-3 mt-2 max-h-64 overflow-auto">
            {detalle.cuerpo || "(sin texto)"}
          </pre>
        </div>
      )}

      {buscado && !cargando && mensajes.length === 0 && (
        <div className="bg-white rounded border border-ms-gray-30 p-8 text-center text-ms-gray-60 text-sm">
          No hay correo borrado guardado de {username}
          {texto ? ` que coincida con «${texto}»` : ""}.
        </div>
      )}
    </div>
  );
}
