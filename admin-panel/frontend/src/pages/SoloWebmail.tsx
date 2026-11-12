import { useEffect, useMemo, useState } from "react";
import { api } from "../api/client";
import { SectionHelp } from "../components/SectionHelp";

interface Indicacion { nivel: "ok" | "info" | "aviso" | "alerta"; texto: string; }
interface Cuenta {
  username: string; nombre: string; protegida: boolean; motivo: string; desde: string | null; por: string;
  dos_pasos: boolean; claves_aplicacion: number; accesos_externos: number; ultimo_acceso_externo: string | null;
  direcciones_con_fallos: number; intentos_fallidos: number; indicacion: Indicacion;
}
interface Respuesta { cuentas: Cuenta[]; dias_de_uso: number; hay_datos_de_uso: boolean; protegidas: number; con_intentos: number; }

const NIVEL: Record<string, string> = {
  ok: "bg-green-50 text-green-700 border-green-200",
  info: "bg-ms-gray-10 text-ms-gray-130 border-ms-gray-30",
  aviso: "bg-amber-50 text-amber-800 border-amber-200",
  alerta: "bg-red-50 text-red-700 border-red-200",
};
const FILTROS = [
  { id: "todas", texto: "Todas" },
  { id: "protegidas", texto: "Protegidas" },
  { id: "alerta", texto: "Con intentos fallidos" },
  { id: "equipos", texto: "Usan Outlook o celular" },
];
const fecha = (t: string | null) => (t ? new Date(t).toLocaleString("es-EC", { dateStyle: "short", timeStyle: "short" }) : "");

export function SoloWebmail() {
  const [datos, setDatos] = useState<Respuesta | null>(null);
  const [buscar, setBuscar] = useState("");
  const [filtro, setFiltro] = useState("todas");
  const [ocupada, setOcupada] = useState("");
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);

  const cargar = () => api.get<Respuesta>("/solo-webmail").then(setDatos).catch((e: any) => setMsg({ ok: false, text: e?.message || "No se pudo cargar la lista" }));
  useEffect(() => { cargar(); }, []);

  const visibles = useMemo(() => {
    const q = buscar.trim().toLowerCase();
    return (datos?.cuentas || []).filter((c) => {
      if (q && !c.username.includes(q) && !c.nombre.toLowerCase().includes(q)) return false;
      if (filtro === "protegidas") return c.protegida;
      if (filtro === "alerta") return c.indicacion.nivel === "alerta";
      if (filtro === "equipos") return c.accesos_externos > 0;
      return true;
    });
  }, [datos, buscar, filtro]);

  const cambiar = async (c: Cuenta) => {
    let motivo = "";
    if (!c.protegida) {
      const aviso = c.accesos_externos > 0 && c.claves_aplicacion === 0
        ? "\n\nATENCIÓN: esta persona usa Outlook o celular con su contraseña. Esos equipos dejarán de recibir y enviar correo hasta que cree una contraseña de aplicación desde su cuenta."
        : "\n\nLa persona no notará nada: el webmail sigue funcionando igual.";
      const r = window.prompt(`Proteger ${c.username}: desde fuera, su contraseña dejará de servir por IMAP, POP3 y SMTP.${aviso}\n\nMotivo (queda en la auditoría):`, c.direcciones_con_fallos >= 3 ? "Intentos de adivinar la contraseña" : "");
      if (r === null) return;
      motivo = r;
    } else if (!window.confirm(`¿Quitar la protección de ${c.username}? Su contraseña volverá a servir desde fuera por IMAP, POP3 y SMTP.`)) return;
    setOcupada(c.username);
    try {
      await api.put(`/solo-webmail/${encodeURIComponent(c.username)}`, { activo: !c.protegida, motivo });
      setMsg({ ok: true, text: c.protegida ? `Protección quitada a ${c.username}.` : `${c.username} quedó protegida. El cambio es inmediato.` });
      await cargar();
    } catch (e: any) { setMsg({ ok: false, text: e?.message || "No se pudo guardar" }); }
    setOcupada("");
  };

  if (!datos) return <div className="p-6 text-sm text-ms-gray-110">{msg ? msg.text : "Cargando…"}</div>;

  return (
    <div className="max-w-5xl">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-ms-gray-160 mb-1">Cuentas solo webmail</h1>
        <SectionHelp titulo="Cuentas solo webmail" items={[
          { titulo: "Qué es esta sección", desc: "Cierra la entrada por IMAP, POP3 y SMTP cuenta por cuenta, sin tocar el resto del servidor. En una cuenta protegida, quien pruebe la contraseña desde fuera recibe «contraseña incorrecta» aunque acierte." },
          { titulo: "Qué sigue funcionando", desc: "El webmail, igual que siempre. Si la persona necesita Outlook o el correo del celular, crea una contraseña de aplicación desde su cuenta: es una clave aparte, solo para ese equipo." },
          { titulo: "Cuándo activarlo", desc: "Cuando una cuenta recibe intentos de adivinar su contraseña, o en cuentas sensibles que solo usan el webmail. La columna «Indicación» dice si se puede activar sin afectar a la persona." },
          { titulo: "Antes de activarlo", desc: "Si la indicación avisa de que la persona usa Outlook o celular, primero debe crear su contraseña de aplicación; si no, esos equipos dejarán de recibir correo." },
          { titulo: "Efecto", desc: "Inmediato, sin reiniciar nada. Cada cambio queda en la auditoría con quién lo hizo y el motivo." },
          { titulo: "Verificación en dos pasos", desc: "Es complementaria: protege la entrada por el webmail. Esta sección protege las otras puertas (IMAP, POP3, SMTP), donde no hay segundo paso." },
        ]} />
      </div>
      <p className="text-sm text-ms-gray-110 mb-4">
        En las cuentas protegidas la contraseña solo sirve en el webmail. Desde Outlook, celulares o cualquier programa externo
        hace falta una contraseña de aplicación; a un atacante el servidor le responde «contraseña incorrecta» aunque acierte.
      </p>
      {msg && <div className={`text-sm mb-4 px-3 py-2 rounded ${msg.ok ? "bg-green-50 text-green-700" : "bg-red-50 text-red-600"}`}>{msg.text}</div>}

      <div className="grid grid-cols-3 gap-3 mb-5">
        <div className="bg-white border border-ms-gray-30 rounded-lg p-4 text-center"><div className="text-2xl font-bold text-green-700">{datos.protegidas}</div><div className="text-xs text-ms-gray-110">Cuentas protegidas</div></div>
        <div className="bg-white border border-ms-gray-30 rounded-lg p-4 text-center"><div className="text-2xl font-bold text-[#d13438]">{datos.con_intentos}</div><div className="text-xs text-ms-gray-110">Con intentos fallidos desde varias direcciones</div></div>
        <div className="bg-white border border-ms-gray-30 rounded-lg p-4 text-center"><div className="text-2xl font-bold text-ms-gray-160">{datos.cuentas.length}</div><div className="text-xs text-ms-gray-110">Cuentas activas</div></div>
      </div>
      {!datos.hay_datos_de_uso && <div className="text-xs mb-3 px-3 py-2 rounded bg-amber-50 text-amber-800">Este servidor no recoge los accesos por servicio: antes de proteger una cuenta, confirme con la persona si usa Outlook o celular.</div>}

      <div className="flex flex-wrap items-center gap-2 mb-3">
        <input className="px-3 py-2 border border-ms-gray-30 rounded text-sm flex-1 min-w-[220px]" placeholder="Buscar por cuenta o nombre…" value={buscar} onChange={(e) => setBuscar(e.target.value)} aria-label="Buscar cuenta" />
        {FILTROS.map((f) => (
          <button key={f.id} onClick={() => setFiltro(f.id)} aria-pressed={filtro === f.id} className={`px-3 py-2 rounded text-xs border ${filtro === f.id ? "bg-ms-blue text-white border-ms-blue" : "bg-white text-ms-gray-160 border-ms-gray-30"}`}>{f.texto}</button>
        ))}
      </div>

      <div className="bg-white border border-ms-gray-30 rounded-lg overflow-hidden">
        {visibles.length === 0 ? <div className="p-4 text-sm text-ms-gray-110">Ninguna cuenta coincide.</div> : visibles.map((c) => (
          <div key={c.username} className="border-t border-ms-gray-10 first:border-0 p-3 flex items-start justify-between gap-3">
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                <span className={`text-xs rounded px-2 py-0.5 border ${c.protegida ? NIVEL.ok : NIVEL.info}`}>{c.protegida ? "ACTIVO" : "Inactivo"}</span>
                <span className="text-sm font-medium text-ms-gray-160">{c.username}</span>
                {c.nombre && <span className="text-xs text-ms-gray-110">{c.nombre}</span>}
              </div>
              <div className={`text-xs mt-1 px-2 py-1 rounded border inline-block ${NIVEL[c.indicacion.nivel] || NIVEL.info}`}>{c.indicacion.texto}</div>
              <div className="text-xs text-ms-gray-110 mt-1 flex flex-wrap gap-x-3">
                <span>Dos pasos: {c.dos_pasos ? "sí" : "no"}</span>
                <span>Contraseñas de aplicación: {c.claves_aplicacion}</span>
                {datos.hay_datos_de_uso && <span>Accesos desde fuera ({datos.dias_de_uso} días): {c.accesos_externos}{c.ultimo_acceso_externo ? `, último ${fecha(c.ultimo_acceso_externo)}` : ""}</span>}
                {c.intentos_fallidos > 0 && <span>Intentos fallidos: {c.intentos_fallidos} desde {c.direcciones_con_fallos} direcciones</span>}
                {c.protegida && <span>Protegida desde {fecha(c.desde)}{c.por ? ` por ${c.por}` : ""}{c.motivo ? ` — ${c.motivo}` : ""}</span>}
              </div>
            </div>
            <button onClick={() => cambiar(c)} disabled={ocupada === c.username}
              title={c.protegida ? "Quita la protección: la contraseña vuelve a servir desde fuera. Pide confirmación." : "Protege la cuenta: desde fuera la contraseña deja de servir por IMAP, POP3 y SMTP. Pide el motivo."}
              className={`shrink-0 px-3 py-1.5 rounded text-xs ${c.protegida ? "bg-ms-gray-20 text-ms-gray-160" : "bg-ms-blue text-white"} disabled:opacity-50`}>
              {c.protegida ? "Quitar protección" : "Proteger"}
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
