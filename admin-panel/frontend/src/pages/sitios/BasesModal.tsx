import { useEffect, useState } from "react";
import { api } from "../../api/client";

interface Base { motor: string; nombre: string }
interface Listado { bases: Base[]; principal: string | null }
interface Creada { base: string; usuario: string; clave: string; servidor: string; puerto: number; motor: string }

const MOTOR: Record<string, string> = { mariadb: "MariaDB", postgresql: "PostgreSQL" };

/* Bases de datos adicionales de un sitio (MariaDB o PostgreSQL) y acceso a phpMyAdmin y Adminer. */
export function BasesModal({ dominio, onCerrar }: { dominio: string; onCerrar: () => void }) {
  const [datos, setDatos] = useState<Listado | null>(null);
  const [creada, setCreada] = useState<Creada | null>(null);
  const [mensaje, setMensaje] = useState("");
  const [ocupado, setOcupado] = useState(false);

  const cargar = () => api.get<Listado>(`/sitios/${dominio}/bases`).then(setDatos).catch((e) => setMensaje(e.message));
  useEffect(() => { cargar(); }, [dominio]);

  const hacer = async (fn: () => Promise<void>) => {
    setOcupado(true); setMensaje("");
    try { await fn(); } catch (e) { setMensaje((e as Error).message); } finally { setOcupado(false); cargar(); }
  };
  const crear = (motor: string) => hacer(async () => { setCreada(await api.post<Creada>(`/sitios/${dominio}/bases`, { motor })); });
  const borrar = (b: Base) => {
    if (!confirm(`Se borrará la base ${b.nombre}. Antes se guarda una copia (.sql) en la carpeta privada del sitio. ¿Continuar?`)) return;
    hacer(async () => {
      const r = await api.del<{ copia: string }>(`/sitios/${dominio}/bases/${b.nombre}`);
      setMensaje(`Base borrada. Copia guardada en ${r.copia}.`);
    });
  };

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4" role="dialog" aria-modal="true">
      <div className="bg-white rounded shadow-lg w-full max-w-xl p-5 space-y-4 max-h-[90vh] overflow-y-auto">
        <h2 className="text-lg font-semibold text-ms-gray-130">Bases de datos — {dominio}</h2>
        {datos?.principal && <p className="text-sm">Base de la aplicación: <code>{datos.principal}</code> (MariaDB). Sus datos de acceso están en la configuración de la aplicación.</p>}
        <div>
          <h3 className="text-sm font-semibold mb-1">Bases adicionales (para aplicaciones propias)</h3>
          {datos && datos.bases.length === 0 && <p className="text-xs text-ms-gray-60">Ninguna.</p>}
          <ul className="text-sm divide-y divide-ms-gray-30">
            {datos?.bases.map((b) => (
              <li key={b.nombre} className="flex justify-between py-1.5">
                <span><code>{b.nombre}</code> <span className="text-xs text-ms-gray-60">{MOTOR[b.motor] || b.motor}</span></span>
                <button onClick={() => borrar(b)} disabled={ocupado} className="text-ms-red hover:underline text-xs disabled:opacity-50">Borrar</button>
              </li>
            ))}
          </ul>
          <div className="flex gap-2 mt-2">
            <button onClick={() => crear("mariadb")} disabled={ocupado} className="px-3 py-1.5 bg-ms-blue text-white rounded text-sm disabled:opacity-50">+ MariaDB</button>
            <button onClick={() => crear("postgresql")} disabled={ocupado} className="px-3 py-1.5 border border-ms-blue text-ms-blue rounded text-sm disabled:opacity-50">+ PostgreSQL</button>
          </div>
        </div>
        {creada && (
          <div className="border border-amber-300 bg-amber-50 rounded p-3 text-sm space-y-1">
            <p className="font-medium">Base {MOTOR[creada.motor]} creada. Guarde estos datos: la contraseña no se vuelve a mostrar.</p>
            <p>Servidor: <code>{creada.servidor}:{creada.puerto}</code> · Base y usuario: <code>{creada.base}</code></p>
            <p>Contraseña: <code className="select-all break-all">{creada.clave}</code></p>
            <p className="text-xs text-ms-gray-90">Solo se puede usar desde este servidor; cada usuario entra únicamente a su base.</p>
          </div>
        )}
        <div className="border-t border-ms-gray-30 pt-3 text-sm space-y-1">
          <h3 className="font-semibold">Administrar el contenido</h3>
          <p className="text-xs text-ms-gray-90">Con el usuario y la contraseña de cada base. Solo se conectan a los servidores de este equipo.</p>
          <div className="flex gap-4">
            <a href="/herramientas/phpmyadmin/" target="_blank" rel="noopener noreferrer" className="text-ms-blue hover:underline">phpMyAdmin (MariaDB)</a>
            <a href="/herramientas/adminer/" target="_blank" rel="noopener noreferrer" className="text-ms-blue hover:underline">Adminer (MariaDB y PostgreSQL)</a>
          </div>
        </div>
        {(ocupado || mensaje) && <p className="text-sm text-ms-gray-90">{ocupado ? "Un momento…" : mensaje}</p>}
        <div className="text-right"><button onClick={onCerrar} className="px-4 py-2 border border-ms-gray-40 rounded text-sm">Cerrar</button></div>
      </div>
    </div>
  );
}
