import { useEffect, useState } from "react";
import { api } from "../../../api/client";
import { botonPrincipal, campo } from "./tipos";

interface Cuenta { nombre: string; usuario: string; carpeta: string; creada?: string; montada: boolean }
interface Datos { cuentas: Cuenta[]; maximo: number; usuario?: string; clave?: string }

/* Cuentas FTP adicionales: otra persona entra solo en una subcarpeta de la carpeta pública (FTPS o SFTP). */
export function FtpCuentasPestana({ dominio, onClave }: { dominio: string; onClave: (usuario: string, clave: string, carpeta: string) => void }) {
  const [datos, setDatos] = useState<Datos | null>(null);
  const [nombre, setNombre] = useState("");
  const [carpeta, setCarpeta] = useState("");
  const [error, setError] = useState("");
  const [ocupado, setOcupado] = useState(false);

  useEffect(() => { api.get<Datos>(`/sitios/${dominio}/ftp/cuentas`).then(setDatos).catch((e) => setError(e.message)); }, [dominio]);

  const hacer = async (fn: () => Promise<Datos>, carpetaCuenta = "") => {
    setOcupado(true); setError("");
    try {
      const d = await fn();
      setDatos(d);
      if (d.usuario && d.clave) onClave(d.usuario, d.clave, carpetaCuenta);
      return true;
    } catch (e) { setError((e as Error).message); return false; } finally { setOcupado(false); }
  };
  const crear = async () => {
    const sub = carpeta.trim().replace(/^\/+|\/+$/g, "");
    if (await hacer(() => api.post<Datos>(`/sitios/${dominio}/ftp/cuentas`, { nombre: nombre.trim(), carpeta: sub }), sub)) { setNombre(""); setCarpeta(""); }
  };

  return (
    <div className="space-y-3">
      <p className="text-xs text-ms-gray-90">Para un diseñador o un proveedor que solo debe tocar una parte del sitio. La cuenta entra con FTP cifrado o SFTP y solo ve su subcarpeta; lo que sube es del sitio, igual que si lo subiera la cuenta principal.</p>
      <div className="border border-ms-gray-30 rounded p-3 flex flex-wrap items-center gap-2">
        <input placeholder="nombre (p. ej. disenio)" value={nombre} onChange={(e) => setNombre(e.target.value.toLowerCase())} maxLength={11} className={`${campo} w-48`} />
        <span className="text-sm text-ms-gray-60">publico/</span>
        <input placeholder="imagenes" value={carpeta} onChange={(e) => setCarpeta(e.target.value)} className={`${campo} font-mono w-56`} />
        <button disabled={ocupado || !nombre.trim() || !carpeta.trim()} onClick={crear} className={botonPrincipal}>Crear cuenta</button>
        <p className="w-full text-[11px] text-ms-gray-60">La subcarpeta tiene que existir (créela antes por FTP). Nombre: de 2 a 11 minúsculas o números, empezando por una letra.</p>
      </div>
      {error && <p className="text-sm text-ms-red">{error}</p>}
      <table className="w-full text-sm">
        <thead className="bg-ms-gray-20 text-xs text-ms-gray-90"><tr>
          <th className="text-left px-2 py-1.5">Usuario</th><th className="text-left px-2 py-1.5">Carpeta</th><th className="text-left px-2 py-1.5">Creada</th><th></th></tr></thead>
        <tbody className="divide-y divide-ms-gray-30">
          {datos?.cuentas.map((c) => (
            <tr key={c.nombre}>
              <td className="px-2 py-1.5 font-mono text-xs">{c.usuario}{!c.montada && <span className="ml-2 text-amber-700" title="La carpeta no está montada: revise que exista y vuelva a crear la cuenta.">sin carpeta</span>}</td>
              <td className="px-2 py-1.5 font-mono text-xs">publico/{c.carpeta}</td>
              <td className="px-2 py-1.5 text-xs text-ms-gray-60">{c.creada}</td>
              <td className="px-2 py-1.5 text-right text-xs whitespace-nowrap space-x-2">
                <button disabled={ocupado} onClick={() => hacer(() => api.post<Datos>(`/sitios/${dominio}/ftp/cuentas/${c.nombre}/clave`), c.carpeta)} className="text-ms-blue hover:underline">Nueva clave</button>
                <button disabled={ocupado} onClick={() => confirm(`¿Quitar la cuenta ${c.usuario}? Los archivos de la carpeta se quedan.`) && hacer(() => api.del<Datos>(`/sitios/${dominio}/ftp/cuentas/${c.nombre}`))} className="text-ms-red hover:underline">Quitar</button>
              </td>
            </tr>
          ))}
          {datos && datos.cuentas.length === 0 && <tr><td colSpan={4} className="px-2 py-4 text-center text-ms-gray-60 text-sm">Sin cuentas adicionales. La cuenta principal se gestiona en la columna «FTP» de la lista.</td></tr>}
        </tbody>
      </table>
      {datos && <p className="text-[11px] text-ms-gray-60">{datos.cuentas.length} de {datos.maximo} cuentas adicionales.</p>}
    </div>
  );
}
