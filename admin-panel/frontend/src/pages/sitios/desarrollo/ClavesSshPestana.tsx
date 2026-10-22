import { useEffect, useState } from "react";
import { api } from "../../../api/client";
import { campo, type ClaveSsh, type Hacer, type ListadoClaves } from "./tipos";

/* Claves SSH de las cuentas SFTP del sitio (la principal y las adicionales), cada una encerrada en su carpeta. */
export function ClavesSshPestana({ dominio, ocupado, hacer }: { dominio: string; ocupado: boolean; hacer: Hacer }) {
  const ruta = `/sitios/${dominio}/ssh/claves`;
  const [datos, setDatos] = useState<ListadoClaves | null>(null);
  const [cuenta, setCuenta] = useState("principal");
  const [clave, setClave] = useState("");
  const [error, setError] = useState("");

  useEffect(() => { api.get<ListadoClaves>(ruta).then(setDatos).catch((e) => setError(e.message)); }, [dominio]);

  const agregar = () => hacer("Clave añadida.", async () => {
    setDatos(await api.post<ListadoClaves>(ruta, { cuenta, clave: clave.trim() }));
    setClave("");
  });
  const borrar = (c: ClaveSsh) => {
    if (!confirm(`La clave ${c.huella} dejará de servir para entrar como ${c.usuario || c.cuenta}. ¿Continuar?`)) return;
    hacer("Clave borrada.", async () => setDatos(await api.del<ListadoClaves>(`${ruta}/${c.id}`)));
  };

  if (!datos) return <p className="text-sm text-ms-gray-60">{error || "Cargando…"}</p>;
  const nombre = (c: string) => (c === "principal" ? "Cuenta principal" : `Cuenta ${c}`);
  return (
    <div className="space-y-4 text-sm">
      <p className="text-xs text-ms-gray-90">
        Entrar por SFTP con clave en vez de contraseña. Se admiten claves ed25519 (recomendada), ECDSA y RSA de 3072 bits o más.
        La cuenta sigue encerrada en su carpeta y sin terminal. Las claves de la cuenta principal solo valen mientras el acceso FTP/SFTP está activado.
      </p>
      {datos.cuentas.map((c) => {
        const suyas = datos.claves.filter((k) => k.cuenta === c.cuenta);
        return (
          <div key={c.cuenta}>
            <h3 className="font-semibold">{nombre(c.cuenta)} <code className="font-normal text-xs">{c.usuario}</code>
              {!c.activa && <span className="ml-2 text-xs text-amber-700">(acceso desactivado: sus claves no valen ahora)</span>}</h3>
            {suyas.length === 0 && <p className="text-xs text-ms-gray-60">Sin claves.</p>}
            <ul className="divide-y divide-ms-gray-30">
              {suyas.map((k) => (
                <li key={k.id} className="flex justify-between gap-2 py-1">
                  <span className="text-xs"><code>{k.huella}</code> · {k.tipo} ({k.bits} bits){k.comentario ? ` · ${k.comentario}` : ""}{k.creada ? ` · ${k.creada}` : ""}</span>
                  <button disabled={ocupado} onClick={() => borrar(k)} className="text-ms-red hover:underline text-xs disabled:opacity-50">Borrar</button>
                </li>
              ))}
            </ul>
          </div>
        );
      })}
      <div className="border-t border-ms-gray-30 pt-3 space-y-2">
        <h3 className="font-semibold">Añadir una clave pública</h3>
        <select className={campo} value={cuenta} onChange={(e) => setCuenta(e.target.value)}>
          {datos.cuentas.map((c) => <option key={c.cuenta} value={c.cuenta}>{nombre(c.cuenta)} ({c.usuario})</option>)}
        </select>
        <textarea className={`${campo} w-full font-mono text-xs`} rows={3} placeholder="ssh-ed25519 AAAA… nombre@equipo" value={clave} onChange={(e) => setClave(e.target.value)} />
        <p className="text-xs text-ms-gray-60">Pegue el contenido del archivo .pub (nunca la clave privada), en una sola línea. Hasta {datos.maximo} claves por cuenta.</p>
        <button disabled={ocupado || !clave.trim() || /[\r\n]/.test(clave.trim())} onClick={agregar}
          className="px-3 py-1.5 bg-ms-blue text-white rounded disabled:opacity-50">Añadir</button>
      </div>
    </div>
  );
}
