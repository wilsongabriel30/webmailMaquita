import { useEffect, useState } from "react";
import { api } from "../api/client";
import { SectionHelp } from "../components/SectionHelp";
import { CredencialesModal, type Credencial } from "./sitios/CredencialesModal";
import { InstalarAppForm } from "./sitios/InstalarAppForm";

interface Sitio {
  dominio: string;
  www: boolean;
  app: string | null;
  app_admin: string | null;
  ssl: boolean;
  ftp: boolean;
  usuario_ftp: string;
  base_datos: string | null;
  php: string | null;
  creado: string;
  ocupado_mb: number;
}
interface Estado { php: string | null; mariadb: boolean; wp_cli: boolean; ftp: boolean; certbot: boolean }
interface Listado { sitios: Sitio[]; estado: Estado }

const NOMBRE_APP: Record<string, string> = { wordpress: "WordPress", joomla: "Joomla" };

export function Sitios() {
  const [datos, setDatos] = useState<Listado | null>(null);
  const [error, setError] = useState("");
  const [ocupado, setOcupado] = useState("");
  const [nuevo, setNuevo] = useState({ dominio: "", con_www: true });
  const [mostrarNuevo, setMostrarNuevo] = useState(false);
  const [instalarEn, setInstalarEn] = useState<string | null>(null);
  const [credenciales, setCredenciales] = useState<{ titulo: string; items: Credencial[]; nota?: string } | null>(null);

  const cargar = () =>
    api.get<Listado>("/sitios").then((d) => { setDatos(d); setError(""); }).catch((e) => setError(e.message));
  useEffect(() => { cargar(); }, []);

  const accion = async (etiqueta: string, fn: () => Promise<void>) => {
    setOcupado(etiqueta); setError("");
    try { await fn(); } catch (e) { setError((e as Error).message); } finally { setOcupado(""); cargar(); }
  };

  const crear = () => accion("Creando el sitio…", async () => {
    await api.post("/sitios", nuevo);
    setNuevo({ dominio: "", con_www: true }); setMostrarNuevo(false);
  });

  const ftp = (s: Sitio, activar: boolean) => accion(activar ? "Generando la clave de FTP…" : "Desactivando el FTP…", async () => {
    const r = await api.post<{ usuario?: string; clave?: string }>(`/sitios/${s.dominio}/ftp`, { accion: activar ? "activar" : "desactivar" });
    if (activar && r.clave) {
      setCredenciales({
        titulo: `Acceso a los archivos de ${s.dominio}`,
        items: [
          { etiqueta: "Servidor", valor: window.location.hostname },
          { etiqueta: "Usuario", valor: r.usuario || s.usuario_ftp },
          { etiqueta: "Contraseña", valor: r.clave, secreto: true },
          { etiqueta: "Carpeta del sitio", valor: "publico" },
        ],
        nota: "Use FTP con cifrado (FTPS explícito, puerto 21) o SFTP (puerto 22). El FTP sin cifrar no se acepta. Esta contraseña no se vuelve a mostrar: si se pierde, genere otra.",
      });
    }
  });

  const ssl = (s: Sitio) => {
    const correo = prompt(`Correo de contacto para el certificado de ${s.dominio} (avisos de Let's Encrypt).\n\nAntes: ${s.dominio}${s.www ? ` y www.${s.dominio}` : ""} deben apuntar en el DNS a la IP pública de este servidor.`);
    if (!correo) return;
    accion("Pidiendo el certificado (puede tardar un minuto)…", async () => { await api.post(`/sitios/${s.dominio}/ssl`, { correo }); });
  };

  const borrar = (s: Sitio) => {
    const conf = prompt(`Se dará de baja ${s.dominio}: deja de publicarse, se borran su usuario, su FTP y su base de datos.\nLos archivos y una copia de la base de datos quedan en la papelera del servidor.\n\nEscriba el dominio para confirmar:`);
    if (conf === null) return;
    accion("Dando de baja el sitio…", async () => { await api.del(`/sitios/${s.dominio}`, { confirmacion: conf }); });
  };

  const est = datos?.estado;
  const listo = !!est?.php && est.mariadb;

  return (
    <div className="p-6 space-y-5">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-ms-gray-130">Sitios web</h1>
        <div className="flex items-center gap-2">
          <SectionHelp titulo="Sitios web" items={[
            { titulo: "Para qué sirve", desc: "Publica páginas web en este mismo servidor, cada una con su dominio, su usuario, su PHP y su base de datos aislados del resto." },
            { titulo: "Crear sitio", desc: "Escriba el dominio sin «www.». El sitio responde también con www. Antes de pedir HTTPS, el dominio debe apuntar a la IP pública del servidor." },
            { titulo: "Aplicaciones", desc: "WordPress o Joomla, ambos software libre (GPL). Se descarga la versión oficial vigente y se verifica antes de instalarla. El usuario y la contraseña del administrador se muestran una sola vez." },
            { titulo: "FTP", desc: "Activa el acceso a los archivos por FTP cifrado (FTPS) o SFTP, encerrado en la carpeta del sitio. «Nueva clave» invalida la anterior." },
            { titulo: "HTTPS", desc: "Pide un certificado gratuito de Let's Encrypt y redirige todo a https. Se renueva solo." },
            { titulo: "Dar de baja", desc: "Deja de publicar el sitio. Archivos y base de datos van a la papelera del servidor (/srv/sitios-papelera), no se borran en el acto." },
          ]} />
          {listo && <button onClick={() => setMostrarNuevo(!mostrarNuevo)} className="px-3 py-1.5 bg-ms-blue text-white rounded text-sm hover:bg-ms-blue-dark">+ Nuevo sitio</button>}
        </div>
      </div>

      {error && <div className="bg-red-50 border border-red-200 text-ms-red rounded px-4 py-2 text-sm">{error}</div>}
      {ocupado && <div className="bg-ms-blue-lighter border border-ms-blue/30 text-ms-blue rounded px-4 py-2 text-sm">{ocupado}</div>}

      {datos && !listo && (
        <div className="bg-amber-50 border border-amber-200 rounded p-4 text-sm text-ms-gray-130">
          Los sitios web aún no están instalados en este servidor. Como administrador del sistema, ejecute:
          <pre className="mt-2 bg-white border rounded p-2 text-xs">sudo bash deploy/webmail/instalar-app.sh sitios</pre>
        </div>
      )}

      {mostrarNuevo && (
        <div className="bg-white rounded border border-ms-gray-30 p-5 flex flex-wrap items-center gap-3">
          <input placeholder="midominio.org" value={nuevo.dominio} onChange={(e) => setNuevo({ ...nuevo, dominio: e.target.value })}
            className="px-3 py-2 border border-ms-gray-40 rounded text-sm w-72 focus:outline-none focus:border-ms-blue" />
          <label className="text-sm text-ms-gray-90 flex items-center gap-1.5">
            <input type="checkbox" checked={nuevo.con_www} onChange={(e) => setNuevo({ ...nuevo, con_www: e.target.checked })} /> También www
          </label>
          <button onClick={crear} disabled={!!ocupado || !nuevo.dominio} className="px-4 py-2 bg-ms-blue text-white rounded text-sm disabled:opacity-50">Crear</button>
          <button onClick={() => setMostrarNuevo(false)} className="px-4 py-2 border border-ms-gray-40 rounded text-sm text-ms-gray-90">Cancelar</button>
        </div>
      )}

      {instalarEn && (
        <InstalarAppForm
          dominio={instalarEn}
          ocupado={!!ocupado}
          onCancelar={() => setInstalarEn(null)}
          onInstalar={(app, titulo, correo) => accion(`Instalando ${NOMBRE_APP[app]} (descarga y verificación: 1–2 minutos)…`, async () => {
            const r = await api.post<{ url_admin: string; admin_usuario: string; admin_clave: string; base_datos: string }>(
              `/sitios/${instalarEn}/app`, { app, titulo, correo });
            setInstalarEn(null);
            setCredenciales({
              titulo: `${NOMBRE_APP[app]} instalado en ${instalarEn}`,
              items: [
                { etiqueta: "Administración", valor: r.url_admin },
                { etiqueta: "Usuario", valor: r.admin_usuario },
                { etiqueta: "Contraseña", valor: r.admin_clave, secreto: true },
                { etiqueta: "Base de datos", valor: r.base_datos },
              ],
              nota: "Guarde estos datos ahora: la contraseña no se vuelve a mostrar. Cámbiela al entrar por primera vez.",
            });
          })}
        />
      )}

      {datos && listo && (
        <div className="bg-white rounded border border-ms-gray-30 overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-ms-gray-20 border-b border-ms-gray-30">
              <tr>
                <th className="text-left px-4 py-2.5 font-medium text-ms-gray-90 text-xs">Sitio</th>
                <th className="text-left px-4 py-2.5 font-medium text-ms-gray-90 text-xs">Aplicación</th>
                <th className="text-center px-4 py-2.5 font-medium text-ms-gray-90 text-xs">HTTPS</th>
                <th className="text-center px-4 py-2.5 font-medium text-ms-gray-90 text-xs">FTP</th>
                <th className="text-right px-4 py-2.5 font-medium text-ms-gray-90 text-xs">Espacio</th>
                <th className="text-right px-4 py-2.5 font-medium text-ms-gray-90 text-xs">Acciones</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-ms-gray-30">
              {datos.sitios.map((s) => (
                <tr key={s.dominio} className="hover:bg-ms-blue-lighter/50">
                  <td className="px-4 py-2.5">
                    <a href={`${s.ssl ? "https" : "http"}://${s.dominio}`} target="_blank" rel="noopener noreferrer" className="font-medium text-ms-gray-130 hover:underline">{s.dominio}</a>
                    <div className="text-[11px] text-ms-gray-60">{s.www ? `y www.${s.dominio} · ` : ""}PHP {s.php} · desde {s.creado}</div>
                  </td>
                  <td className="px-4 py-2.5">
                    {s.app ? (
                      <span>{NOMBRE_APP[s.app] || s.app}{s.app_admin && <> · <a href={s.app_admin} target="_blank" rel="noopener noreferrer" className="text-ms-blue hover:underline text-xs">administrar</a></>}</span>
                    ) : (
                      <button onClick={() => setInstalarEn(s.dominio)} disabled={!!ocupado} className="text-ms-blue hover:underline text-xs disabled:opacity-50">Instalar WordPress o Joomla</button>
                    )}
                  </td>
                  <td className="px-4 py-2.5 text-center">
                    {s.ssl ? <span className="px-2 py-0.5 rounded text-[10px] font-medium bg-green-50 text-ms-green">Activo</span>
                      : <button onClick={() => ssl(s)} disabled={!!ocupado} className="text-ms-blue hover:underline text-xs disabled:opacity-50">Activar</button>}
                  </td>
                  <td className="px-4 py-2.5 text-center text-xs">
                    {s.ftp ? (
                      <>
                        <button onClick={() => ftp(s, true)} disabled={!!ocupado} className="text-ms-blue hover:underline mr-2 disabled:opacity-50">Nueva clave</button>
                        <button onClick={() => ftp(s, false)} disabled={!!ocupado} className="text-ms-gray-90 hover:underline disabled:opacity-50">Desactivar</button>
                      </>
                    ) : (
                      <button onClick={() => ftp(s, true)} disabled={!!ocupado} className="text-ms-blue hover:underline disabled:opacity-50">Activar</button>
                    )}
                  </td>
                  <td className="px-4 py-2.5 text-right text-ms-gray-90">{s.ocupado_mb} MB</td>
                  <td className="px-4 py-2.5 text-right">
                    <button onClick={() => borrar(s)} disabled={!!ocupado} className="text-ms-red hover:underline text-xs disabled:opacity-50">Dar de baja</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {datos.sitios.length === 0 && <div className="p-8 text-center text-ms-gray-60 text-sm">Todavía no hay sitios. Use «+ Nuevo sitio».</div>}
        </div>
      )}

      {credenciales && <CredencialesModal {...credenciales} onCerrar={() => setCredenciales(null)} />}
    </div>
  );
}
