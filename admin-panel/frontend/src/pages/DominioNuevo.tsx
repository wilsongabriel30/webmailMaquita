import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import { SectionHelp } from "../components/SectionHelp";
import { Comprobacion } from "./dns/Comprobacion";
import { CredencialesModal, type Credencial } from "./sitios/CredencialesModal";

interface Resultado {
  dominio: string;
  pasos: { paso: string; estado: string }[];
  registrador: { servidor: string; ip: string }[];
}

const NOMBRE_PASO: Record<string, string> = { correo: "Correo del dominio", dns: "Zona DNS completa (con DKIM)", web: "Sitio web «en construcción»", buzon: "Primer buzón", postmaster: "postmaster@ (informes DMARC y TLS)" };

/* Contraseña fuerte generada en el navegador (no viaja al servidor más que para crear el buzón). */
function claveAleatoria(n = 16) {
  const abc = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789";
  const v = new Uint32Array(n);
  crypto.getRandomValues(v);
  return Array.from(v, (x) => abc[x % abc.length]).join("") + "#" + (v[0] % 10);
}

export function DominioNuevo() {
  const navigate = useNavigate();
  const [form, setForm] = useState({ dominio: "", nombre: "", con_web: true, buzon: "info" });
  const [ocupado, setOcupado] = useState("");
  const [error, setError] = useState("");
  const [res, setRes] = useState<Resultado | null>(null);
  const [cred, setCred] = useState<Credencial[] | null>(null);

  const crear = async () => {
    setError(""); setOcupado("Creando correo, DNS y sitio…");
    try {
      const r = await api.post<Resultado>("/dominio-nuevo", { dominio: form.dominio.trim().toLowerCase(), nombre: form.nombre.trim(), con_web: form.con_web });
      const pasos = [...r.pasos];
      const local = form.buzon.trim().toLowerCase();
      if (local) {
        const direccion = `${local}@${r.dominio}`;
        const clave = claveAleatoria();
        try {
          await api.post("/mailboxes", { username: direccion, password: clave, name: form.nombre.trim(), quota: 0 });
          pasos.push({ paso: "buzon", estado: "creado" });
          setCred([
            { etiqueta: "Correo", valor: direccion },
            { etiqueta: "Contraseña", valor: clave, secreto: true },
            { etiqueta: "Webmail", valor: `https://mail.${r.dominio}/webmail/` },
          ]);
        } catch (e) {
          pasos.push({ paso: "buzon", estado: `no creado: ${(e as Error).message}` });
        }
        try {
          await api.post("/aliases", { address: `postmaster@${r.dominio}`, goto: direccion });
          pasos.push({ paso: "postmaster", estado: `creado → ${direccion}` });
        } catch (e) {
          pasos.push({ paso: "postmaster", estado: `no creado: ${(e as Error).message}` });
        }
      }
      setRes({ ...r, pasos });
    } catch (e) { setError((e as Error).message); } finally { setOcupado(""); }
  };

  const campo = "px-3 py-2 border border-ms-gray-40 rounded text-sm focus:outline-none focus:border-ms-blue w-full";
  return (
    <div className="p-6 space-y-5 max-w-4xl">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-ms-gray-130">Nuevo dominio</h1>
        <SectionHelp titulo="Nuevo dominio" items={[
          { titulo: "Para qué sirve", desc: "Con el dominio y el nombre de la institución deja listos en un paso el correo, la zona DNS completa, el sitio web «en construcción» y el primer buzón." },
          { titulo: "Antes", desc: "Complete una vez «Zonas DNS → Ajustes» (IP pública y servidores de nombres)." },
          { titulo: "Después", desc: "Ponga en el registrador del dominio los servidores de nombres que se muestran, con sus IP. El semáforo avisa cuando Internet ya lo ve; entonces se piden los certificados HTTPS." },
        ]} />
      </div>
      {error && <div className="bg-red-50 border border-red-200 text-ms-red rounded px-4 py-2 text-sm">{error}</div>}

      {!res && (
        <div className="bg-white rounded border border-ms-gray-30 p-5 space-y-4">
          <div className="grid sm:grid-cols-2 gap-4">
            <label className="text-sm text-ms-gray-90">Dominio
              <input value={form.dominio} onChange={(e) => setForm({ ...form, dominio: e.target.value })} placeholder="miorganizacion.org" className={`${campo} mt-1`} /></label>
            <label className="text-sm text-ms-gray-90">Nombre de la institución
              <input value={form.nombre} maxLength={100} onChange={(e) => setForm({ ...form, nombre: e.target.value })} placeholder="Fundación …" className={`${campo} mt-1`} /></label>
            <label className="text-sm text-ms-gray-90">Primer buzón (vacío = ninguno)
              <div className="flex items-center mt-1"><input value={form.buzon} onChange={(e) => setForm({ ...form, buzon: e.target.value })} className={campo} /><span className="ml-2 text-ms-gray-60 whitespace-nowrap">@{form.dominio || "dominio"}</span></div></label>
            <label className="text-sm text-ms-gray-90 flex items-center gap-2 mt-6">
              <input type="checkbox" checked={form.con_web} onChange={(e) => setForm({ ...form, con_web: e.target.checked })} /> También sitio web</label>
          </div>
          <button onClick={crear} disabled={!!ocupado || !form.dominio.trim() || form.nombre.trim().length < 2} className="px-4 py-2 bg-ms-blue text-white rounded text-sm disabled:opacity-50">
            {ocupado || "Crear todo"}</button>
        </div>
      )}

      {res && (
        <>
          <div className="bg-white rounded border border-ms-gray-30 p-5 space-y-2">
            <h2 className="font-semibold text-ms-gray-130">{res.dominio}</h2>
            <ul className="text-sm space-y-1">
              {res.pasos.map((p) => (
                <li key={p.paso}><span className={p.estado.startsWith("no ") ? "text-ms-red" : "text-ms-green"}>●</span> {NOMBRE_PASO[p.paso] || p.paso}: {p.estado}</li>
              ))}
            </ul>
          </div>
          <div className="bg-white rounded border border-ms-gray-30 p-5 space-y-2">
            <h3 className="font-semibold text-ms-gray-130 text-sm">En el registrador del dominio</h3>
            <p className="text-xs text-ms-gray-90">Cambie los servidores de nombres por estos. Como están dentro del propio dominio, el registrador pedirá también su IP (registros de enlace o «glue»).</p>
            <table className="text-sm">
              <tbody>{res.registrador.map((n) => <tr key={n.servidor}><td className="pr-6 font-mono">{n.servidor}</td><td className="font-mono">{n.ip}</td></tr>)}</tbody>
            </table>
          </div>
          <Comprobacion zona={res.dominio} automatica />
          <div className="flex gap-3 text-sm">
            <button onClick={() => navigate(`/dns?zona=${res.dominio}`)} className="text-ms-blue hover:underline">Ver la zona DNS</button>
            <button onClick={() => navigate("/sitios")} className="text-ms-blue hover:underline">Sitios web</button>
            <button onClick={() => { setRes(null); setForm({ dominio: "", nombre: "", con_web: true, buzon: "info" }); }} className="text-ms-blue hover:underline">Otro dominio</button>
          </div>
        </>
      )}
      {cred && <CredencialesModal titulo="Primer buzón" items={cred} nota="Guarde la contraseña: no se vuelve a mostrar. El webmail funcionará con este nombre cuando el DNS haya propagado y tenga certificado." onCerrar={() => setCred(null)} />}
    </div>
  );
}
