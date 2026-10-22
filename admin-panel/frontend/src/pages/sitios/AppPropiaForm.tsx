import { useState } from "react";
import { AutenticacionGit } from "./AutenticacionGit";

export interface NuevaPropia {
  tipo: "estatico" | "python" | "node";
  git?: string; rama?: string; carpeta?: string; spa?: boolean;
  modo?: "wsgi" | "asgi"; entrada?: string; puerto_publico?: number; protocolo?: "tcp" | "udp";
}

const TIPOS = [
  { id: "estatico", nombre: "Estática", desc: "HTML, CSS y JavaScript (también React, Vue o Svelte ya compilados). La sirve nginx, sin PHP." },
  { id: "python", nombre: "Python", desc: "Flask, Django, FastAPI… Entorno virtual propio, gunicorn o uvicorn, requirements.txt." },
  { id: "node", nombre: "Node.js", desc: "Express, Next, Nest… «npm ci» con package-lock.json y la app en el puerto PORT." },
] as const;

const campo = "px-3 py-2 border border-ms-gray-40 rounded text-sm focus:outline-none focus:border-ms-blue";

/* Alta de una aplicación propia en un sitio vacío. */
export function AppPropiaForm({ dominio, ocupado, onCancelar, onCrear }: {
  dominio: string; ocupado: boolean; onCancelar: () => void; onCrear: (datos: NuevaPropia) => void;
}) {
  const [d, setD] = useState<NuevaPropia>({ tipo: "python", modo: "wsgi", protocolo: "tcp" });
  const [conPuerto, setConPuerto] = useState(false);
  const pon = (cambio: Partial<NuevaPropia>) => setD({ ...d, ...cambio });
  const enviar = () => {
    const limpio: NuevaPropia = { tipo: d.tipo, git: d.git?.trim() || undefined, rama: d.rama?.trim() || undefined };
    if (d.tipo === "estatico") Object.assign(limpio, { carpeta: d.carpeta?.trim() || undefined, spa: !!d.spa });
    else {
      Object.assign(limpio, { entrada: d.entrada?.trim() || undefined, modo: d.tipo === "python" ? d.modo : undefined });
      if (conPuerto && d.puerto_publico) Object.assign(limpio, { puerto_publico: d.puerto_publico, protocolo: d.protocolo });
    }
    onCrear(limpio);
  };

  return (
    <div className="bg-white rounded border border-ms-gray-30 p-5 space-y-4">
      <h2 className="text-base font-semibold text-ms-gray-130">Aplicación propia en {dominio}</h2>
      <div className="grid sm:grid-cols-3 gap-3">
        {TIPOS.map((t) => (
          <label key={t.id} className={`border rounded p-3 cursor-pointer ${d.tipo === t.id ? "border-ms-blue bg-ms-blue-lighter/50" : "border-ms-gray-30"}`}>
            <input type="radio" name="tipo" checked={d.tipo === t.id} onChange={() => pon({ tipo: t.id })} className="mr-2" />
            <span className="font-medium">{t.nombre}</span>
            <span className="block text-xs text-ms-gray-90 mt-1">{t.desc}</span>
          </label>
        ))}
      </div>

      <div className="space-y-2">
        <p className="text-xs text-ms-gray-90">Código: deje el repositorio vacío para subirlo por SFTP a la carpeta <code>app</code>
          {d.tipo === "estatico" ? <> (las estáticas sin repositorio se suben a <code>publico</code>)</> : <> (mientras tanto queda una aplicación de ejemplo)</>}.</p>
        <div className="grid sm:grid-cols-[1fr_10rem] gap-2">
          <input value={d.git || ""} onChange={(e) => pon({ git: e.target.value })} placeholder="git@github.com:organizacion/proyecto.git o https://… si es público" className={campo} />
          <input value={d.rama || ""} onChange={(e) => pon({ rama: e.target.value })} placeholder="Rama (opcional)" className={campo} />
        </div>
        {d.git?.trim() && <AutenticacionGit dominio={dominio} repo={d.git} />}
      </div>

      {d.tipo === "estatico" ? (
        <div className="grid sm:grid-cols-2 gap-2 items-center">
          <input value={d.carpeta || ""} disabled={!d.git} onChange={(e) => pon({ carpeta: e.target.value })} placeholder="Carpeta a publicar del repositorio (p. ej. dist)" className={`${campo} disabled:bg-ms-gray-20`} />
          <label className="text-sm"><input type="checkbox" checked={!!d.spa} onChange={(e) => pon({ spa: e.target.checked })} className="mr-2" />Aplicación de una sola página (rutas a index.html)</label>
        </div>
      ) : (
        <div className="space-y-2">
          <div className="grid sm:grid-cols-2 gap-2">
            {d.tipo === "python" && (
              <select value={d.modo} onChange={(e) => pon({ modo: e.target.value as "wsgi" | "asgi" })} className={campo}>
                <option value="wsgi">WSGI (Flask, Django) — gunicorn</option>
                <option value="asgi">ASGI (FastAPI, Starlette) — uvicorn</option>
              </select>
            )}
            <input value={d.entrada || ""} onChange={(e) => pon({ entrada: e.target.value })}
              placeholder={d.tipo === "python" ? "Entrada: app:app o proyecto.wsgi:application" : "Entrada: server.js o «npm start»"} className={campo} />
          </div>
          <label className="text-sm block"><input type="checkbox" checked={conPuerto} onChange={(e) => setConPuerto(e.target.checked)} className="mr-2" />
            Además necesita un puerto público propio (servicio que no es web: MQTT, juegos, sockets…)</label>
          {conPuerto && (
            <div className="flex flex-wrap gap-2 items-center">
              <input type="number" min={1024} max={65535} value={d.puerto_publico || ""} onChange={(e) => pon({ puerto_publico: Number(e.target.value) || undefined })} placeholder="Puerto" className={`${campo} w-28`} />
              <select value={d.protocolo} onChange={(e) => pon({ protocolo: e.target.value as "tcp" | "udp" })} className={campo}><option>tcp</option><option>udp</option></select>
              <span className="text-xs text-ms-gray-90">La aplicación lo recibe en <code>PUERTO_PUBLICO</code> y el cortafuegos lo abre a Internet mientras la aplicación exista.</span>
            </div>
          )}
          <p className="text-xs text-ms-gray-90">La aplicación debe escuchar en <code>HOST</code>:<code>PORT</code> (127.0.0.1 y el puerto que le da el panel); nginx la publica en el dominio con HTTPS y el cortafuegos de aplicación.</p>
        </div>
      )}

      <div className="flex gap-2">
        <button onClick={enviar} disabled={ocupado || (conPuerto && !d.puerto_publico)} className="px-4 py-2 bg-ms-blue text-white rounded text-sm disabled:opacity-50">Crear</button>
        <button onClick={onCancelar} className="px-4 py-2 border border-ms-gray-40 rounded text-sm text-ms-gray-90">Cancelar</button>
      </div>
    </div>
  );
}
