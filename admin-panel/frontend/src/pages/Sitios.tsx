import { useEffect, useState } from "react";
import { api } from "../api/client";
import { SectionHelp } from "../components/SectionHelp";
import { CredencialesModal, type Credencial } from "./sitios/CredencialesModal";
import { APPS, InstalarAppForm } from "./sitios/InstalarAppForm";
import { BasesModal } from "./sitios/BasesModal";
import { AppPropiaForm, type NuevaPropia } from "./sitios/AppPropiaForm";
import { PropiaModal } from "./sitios/PropiaModal";
import { SeguridadModal } from "./sitios/SeguridadModal";
import { BuscadoresModal } from "./sitios/BuscadoresModal";

interface Sitio {
  dominio: string;
  www: boolean;
  app: string | null;
  app_admin: string | null;
  ssl: boolean;
  ftp: boolean;
  tienda?: boolean;
  propia?: string | null;
  bases?: number;
  usuario_ftp: string;
  base_datos: string | null;
  php: string | null;
  creado: string;
  ocupado_mb: number;
}
interface Estado { php: string | null; mariadb: boolean; wp_cli: boolean; ftp: boolean; certbot: boolean }
interface Listado { sitios: Sitio[]; estado: Estado }

const NOMBRE_APP: Record<string, string> = Object.fromEntries(APPS.map((a) => [a.id, a.nombre]));
const NOMBRE_PROPIA: Record<string, string> = { estatico: "Propia · estática", python: "Propia · Python", node: "Propia · Node.js" };

export function Sitios() {
  const [datos, setDatos] = useState<Listado | null>(null);
  const [error, setError] = useState("");
  const [ocupado, setOcupado] = useState("");
  const [nuevo, setNuevo] = useState({ dominio: "", con_www: true });
  const [mostrarNuevo, setMostrarNuevo] = useState(false);
  const [instalarEn, setInstalarEn] = useState<string | null>(null);
  const [seguridadDe, setSeguridadDe] = useState<string | null>(null);
  const [buscadoresDe, setBuscadoresDe] = useState<string | null>(null);
  const [basesDe, setBasesDe] = useState<string | null>(null);
  const [propiaEn, setPropiaEn] = useState<string | null>(null);
  const [gestionarDe, setGestionarDe] = useState<string | null>(null);
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

  // La pestaña se abre ANTES de pedir el enlace: si se abre después del await, el navegador la bloquea.
  const entrar = (s: Sitio) => {
    const pestana = window.open("about:blank", "_blank");
    accion("Generando el acceso…", async () => {
      try {
        const r = await api.post<{ url: string }>(`/sitios/${s.dominio}/entrar`);
        if (pestana) { pestana.opener = null; pestana.location.href = r.url; } else { window.location.href = r.url; }
      } catch (e) { pestana?.close(); throw e; }
    });
  };

  const nuevaClave = (s: Sitio) => {
    if (!confirm(`Se generará una contraseña nueva para el administrador de ${s.dominio}. La anterior deja de valer. ¿Continuar?`)) return;
    accion("Generando la contraseña…", async () => {
      const r = await api.post<{ usuario: string; clave: string; url_admin: string }>(`/sitios/${s.dominio}/clave-admin`);
      setCredenciales({
        titulo: `Nueva contraseña del administrador de ${s.dominio}`,
        items: [
          { etiqueta: "Administración", valor: r.url_admin },
          { etiqueta: "Usuario", valor: r.usuario },
          { etiqueta: "Contraseña", valor: r.clave, secreto: true },
        ],
        nota: "Esta contraseña no se vuelve a mostrar.",
      });
    });
  };

  const tienda = (s: Sitio) => {
    if (!confirm(`Se instalará WooCommerce (tienda en línea, GPLv3) en ${s.dominio}. ¿Continuar?`)) return;
    accion("Instalando WooCommerce…", async () => {
      const r = await api.post<{ url_admin: string }>(`/sitios/${s.dominio}/tienda`);
      setCredenciales({ titulo: `Tienda instalada en ${s.dominio}`, items: [{ etiqueta: "Configurar la tienda", valor: r.url_admin }],
        nota: "Entre al escritorio de WordPress y siga el asistente de WooCommerce (moneda, pagos y envíos)." });
    });
  };

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
            { titulo: "Entrar y contraseña", desc: "«Entrar» abre el escritorio de WordPress sin contraseña con un enlace de un solo uso que vence en 60 segundos. «Nueva contraseña» genera otra para el administrador (WordPress o Joomla) si se olvidó." },
            { titulo: "Seguridad", desc: "Cada sitio tiene cortafuegos de aplicación (OWASP CRS), límite de intentos de inicio de sesión y bloqueo automático de IP atacantes. En WordPress además: XML-RPC y enumeración de usuarios cerrados, versión oculta, editor de archivos apagado, segundo factor disponible y actualizaciones automáticas. «Seguridad» muestra versión, actualizaciones pendientes y si los archivos del núcleo fueron alterados." },
            { titulo: "Aplicaciones", desc: "WordPress (con tienda WooCommerce opcional), Joomla, Moodle (aula virtual), Dolibarr (ERP y CRM) y Matomo (estadísticas). Todo software libre, descargado de su origen oficial y verificado con su suma publicada." },
            { titulo: "Aplicaciones propias", desc: "Su propio código: estático (HTML/JS), Python (Flask, Django, FastAPI) o Node.js, subido por SFTP o desde un repositorio git. Python y Node corren como servicio encerrado con el usuario del sitio, detrás de nginx y del cortafuegos de aplicación; variables de entorno, registros y despliegue desde «Gestionar». Si necesitan un puerto propio, el cortafuegos lo abre solo." },
            { titulo: "Bases de datos", desc: "Cada sitio puede tener hasta 10 bases adicionales MariaDB o PostgreSQL para aplicaciones propias, con usuario propio que solo entra a su base. Su contenido se administra con phpMyAdmin o Adminer dentro del panel." },
            { titulo: "Buscadores", desc: "Revisa el sitio como un buscador (robots.txt, mapa del sitio, llms.txt para asistentes de IA, datos schema.org, HTTPS), avisa al momento a Bing y otros por IndexNow y pone en el DNS la verificación de Google Search Console." },
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

      {propiaEn && (
        <AppPropiaForm
          dominio={propiaEn}
          ocupado={!!ocupado}
          onCancelar={() => setPropiaEn(null)}
          onCrear={(datos: NuevaPropia) => accion(`Preparando la aplicación${datos.git ? " (clonando el repositorio)" : ""}${datos.tipo === "estatico" ? "" : " e instalando dependencias"}…`, async () => {
            await api.post(`/sitios/${propiaEn}/propia`, datos);
            const dominio = propiaEn;
            setPropiaEn(null);
            setGestionarDe(dominio);
          })}
        />
      )}

      {instalarEn && (
        <InstalarAppForm
          dominio={instalarEn}
          ocupado={!!ocupado}
          onCancelar={() => setInstalarEn(null)}
          onInstalar={(app, titulo, correo) => accion(`Instalando ${NOMBRE_APP[app]} (descarga, verificación e instalación: ${app === "moodle" ? "unos 5 minutos" : "1–2 minutos"})…`, async () => {
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
                    {s.app === "propia" ? (
                      <div>
                        <span>{NOMBRE_PROPIA[s.propia || ""] || "Aplicación propia"}</span>
                        <div className="text-xs mt-0.5"><button onClick={() => setGestionarDe(s.dominio)} disabled={!!ocupado} className="text-ms-blue hover:underline disabled:opacity-50">Gestionar</button></div>
                      </div>
                    ) : s.app ? (
                      <div>
                        <span>{NOMBRE_APP[s.app] || s.app}</span>
                        <div className="text-xs mt-0.5 space-x-2">
                          {s.app === "wordpress" && <button onClick={() => entrar(s)} disabled={!!ocupado} title="Abre el escritorio de WordPress sin contraseña (enlace de un solo uso, 60 segundos)." className="text-ms-blue hover:underline disabled:opacity-50">Entrar</button>}
                          {s.app !== "wordpress" && s.app_admin && <a href={s.app_admin} target="_blank" rel="noopener noreferrer" className="text-ms-blue hover:underline">Administrar</a>}
                          <button onClick={() => nuevaClave(s)} disabled={!!ocupado} className="text-ms-blue hover:underline disabled:opacity-50">Nueva contraseña</button>
                          <button onClick={() => setSeguridadDe(s.dominio)} disabled={!!ocupado} className="text-ms-blue hover:underline disabled:opacity-50">Seguridad</button>
                          {s.app === "wordpress" && !s.tienda && <button onClick={() => tienda(s)} disabled={!!ocupado} title="WooCommerce: tienda en línea libre." className="text-ms-blue hover:underline disabled:opacity-50">Tienda</button>}
                        </div>
                      </div>
                    ) : (
                      <span>
                      <button onClick={() => setInstalarEn(s.dominio)} disabled={!!ocupado} className="text-ms-blue hover:underline text-xs disabled:opacity-50">Instalar una aplicación</button>
                      <span className="text-ms-gray-60 text-xs"> · </span>
                      <button onClick={() => setPropiaEn(s.dominio)} disabled={!!ocupado} title="Su propio código: HTML/JS, Python o Node.js." className="text-ms-blue hover:underline text-xs disabled:opacity-50">Aplicación propia</button>
                      </span>
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
                  <td className="px-4 py-2.5 text-right whitespace-nowrap">
                    <button onClick={() => setBuscadoresDe(s.dominio)} disabled={!!ocupado} title="Visibilidad en buscadores e IA: revisión, aviso a Bing y otros, verificación de Google." className="text-ms-blue hover:underline text-xs mr-3 disabled:opacity-50">Buscadores</button>
                    <button onClick={() => setBasesDe(s.dominio)} disabled={!!ocupado} title="Bases de datos adicionales (MariaDB o PostgreSQL), phpMyAdmin y Adminer." className="text-ms-blue hover:underline text-xs mr-3 disabled:opacity-50">Bases{s.bases ? ` (${s.bases})` : ""}</button>
                    <button onClick={() => borrar(s)} disabled={!!ocupado} className="text-ms-red hover:underline text-xs disabled:opacity-50">Dar de baja</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {datos.sitios.length === 0 && <div className="p-8 text-center text-ms-gray-60 text-sm">Todavía no hay sitios. Use «+ Nuevo sitio».</div>}
        </div>
      )}

      {gestionarDe && <PropiaModal dominio={gestionarDe} onCerrar={() => { setGestionarDe(null); cargar(); }} />}
      {basesDe && <BasesModal dominio={basesDe} onCerrar={() => { setBasesDe(null); cargar(); }} />}
      {buscadoresDe && <BuscadoresModal dominio={buscadoresDe} onCerrar={() => setBuscadoresDe(null)} />}
      {seguridadDe && <SeguridadModal dominio={seguridadDe} onCerrar={() => { setSeguridadDe(null); cargar(); }} />}
      {credenciales && <CredencialesModal {...credenciales} onCerrar={() => setCredenciales(null)} />}
    </div>
  );
}
