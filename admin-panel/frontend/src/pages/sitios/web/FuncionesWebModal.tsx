import { useEffect, useState } from "react";
import { api } from "../../../api/client";
import { CredencialesModal, type Credencial } from "../CredencialesModal";
import type { EstadoWeb } from "./tipos";
import { RedireccionesPestana } from "./RedireccionesPestana";
import { PrivacidadPestana } from "./PrivacidadPestana";
import { ErroresPestana } from "./ErroresPestana";
import { HotlinkPestana } from "./HotlinkPestana";
import { BloqueoIpPestana } from "./BloqueoIpPestana";
import { OptimizacionPestana } from "./OptimizacionPestana";
import { FtpCuentasPestana } from "./FtpCuentasPestana";

export type PestanaWeb = "redirecciones" | "privacidad" | "errores" | "hotlink" | "bloqueo" | "optimizacion" | "ftp";

const PESTANAS: { id: PestanaWeb; nombre: string }[] = [
  { id: "redirecciones", nombre: "Redirecciones" },
  { id: "privacidad", nombre: "Carpetas con contraseña" },
  { id: "errores", nombre: "Páginas de error" },
  { id: "hotlink", nombre: "Hotlinking" },
  { id: "bloqueo", nombre: "IP bloqueadas" },
  { id: "optimizacion", nombre: "Optimización" },
  { id: "ftp", nombre: "Cuentas FTP" },
];

/* Funciones web del sitio (como en un panel de hospedaje): cada cambio se comprueba con nginx antes de aplicarse;
   si nginx lo rechaza, el sitio sigue con la configuración anterior y aquí se muestra el motivo. */
export function FuncionesWebModal({ dominio, inicial = "redirecciones", onCerrar }: { dominio: string; inicial?: PestanaWeb; onCerrar: () => void }) {
  const [estado, setEstado] = useState<EstadoWeb | null>(null);
  const [pestana, setPestana] = useState<PestanaWeb>(inicial);
  const [mensaje, setMensaje] = useState("");
  const [error, setError] = useState("");
  const [ocupado, setOcupado] = useState(false);
  const [credenciales, setCredenciales] = useState<{ titulo: string; items: Credencial[]; nota?: string } | null>(null);

  useEffect(() => { api.get<EstadoWeb>(`/sitios/${dominio}/web`).then(setEstado).catch((e) => setError(e.message)); }, [dominio]);

  const hacer = async (texto: string, fn: () => Promise<EstadoWeb | void>) => {
    setOcupado(true); setError(""); setMensaje("");
    try {
      const e = await fn();
      if (e && "redirecciones" in e) setEstado(e);
      setMensaje(texto);
      return true;
    } catch (e) { setError((e as Error).message); return false; } finally { setOcupado(false); }
  };
  const boton = (activo: boolean) => `px-3 py-1.5 text-sm rounded-t border-b-2 whitespace-nowrap ${activo ? "border-ms-blue text-ms-blue" : "border-transparent text-ms-gray-90"}`;
  const props = estado ? { dominio, estado, ocupado, hacer } : null;

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4" role="dialog" aria-modal="true">
      <div className="bg-white rounded shadow-lg w-full max-w-4xl p-5 space-y-3 max-h-[92vh] overflow-y-auto">
        <div className="flex justify-between items-start">
          <div>
            <h2 className="text-lg font-semibold text-ms-gray-130">Funciones web — {dominio}</h2>
            <p className="text-xs text-ms-gray-90">Cada cambio se comprueba con nginx antes de aplicarse: si lo rechaza, el sitio sigue como estaba y se muestra el motivo.</p>
          </div>
          <button onClick={onCerrar} className="text-sm text-ms-gray-90 hover:underline">Cerrar</button>
        </div>
        <div className="flex gap-1 border-b border-ms-gray-30 overflow-x-auto">
          {PESTANAS.map((p) => <button key={p.id} className={boton(pestana === p.id)} onClick={() => { setPestana(p.id); setMensaje(""); setError(""); }}>{p.nombre}</button>)}
        </div>
        {!estado && !error && <p className="text-sm text-ms-gray-60">Cargando…</p>}

        {props && pestana === "redirecciones" && <RedireccionesPestana {...props} />}
        {props && pestana === "privacidad" && <PrivacidadPestana {...props} onClave={(carpeta, usuario, clave) => setCredenciales({
          titulo: `Acceso a ${carpeta}`,
          items: [{ etiqueta: "Dirección", valor: `${dominio}${carpeta}/` }, { etiqueta: "Usuario", valor: usuario }, { etiqueta: "Contraseña", valor: clave, secreto: true }],
          nota: "Guarde la contraseña ahora: no se vuelve a mostrar. Si se pierde, vuelva a añadir el mismo usuario para darle otra.",
        })} />}
        {props && pestana === "errores" && <ErroresPestana {...props} />}
        {props && pestana === "hotlink" && <HotlinkPestana {...props} />}
        {props && pestana === "bloqueo" && <BloqueoIpPestana {...props} />}
        {props && pestana === "optimizacion" && <OptimizacionPestana {...props} />}
        {pestana === "ftp" && <FtpCuentasPestana dominio={dominio} onClave={(usuario, clave, carpeta) => setCredenciales({
          titulo: `Cuenta FTP ${usuario}`,
          items: [{ etiqueta: "Servidor", valor: dominio }, { etiqueta: "Usuario", valor: usuario }, { etiqueta: "Contraseña", valor: clave, secreto: true },
            { etiqueta: "Carpeta", valor: `archivos/ → publico/${carpeta}` }],
          nota: "FTP con cifrado (FTPS explícito, puerto 21) o SFTP (puerto 22). La cuenta solo ve su subcarpeta, dentro de «archivos». Guarde la contraseña ahora: no se vuelve a mostrar.",
        })} />}

        {(mensaje || error) && <p className={`text-sm ${error ? "text-ms-red" : "text-ms-green"}`}>{error || mensaje}</p>}
      </div>
      {credenciales && <CredencialesModal {...credenciales} onCerrar={() => setCredenciales(null)} />}
    </div>
  );
}
