import { useState } from "react";

const APPS = [
  { id: "wordpress", nombre: "WordPress", desc: "Sitios, blogs y noticias. El más usado; miles de plantillas y complementos libres." },
  { id: "joomla", nombre: "Joomla", desc: "Portales con varias secciones, usuarios registrados y varios idiomas." },
];

/* Elegir aplicación (software libre, GPL) para un sitio vacío. */
export function InstalarAppForm({ dominio, ocupado, onCancelar, onInstalar }: {
  dominio: string;
  ocupado: boolean;
  onCancelar: () => void;
  onInstalar: (app: string, titulo: string, correo: string) => void;
}) {
  const [app, setApp] = useState("wordpress");
  const [titulo, setTitulo] = useState("");
  const [correo, setCorreo] = useState("");
  return (
    <div className="bg-white rounded border border-ms-gray-30 p-5 space-y-4">
      <h2 className="text-base font-semibold text-ms-gray-130">Instalar una aplicación en {dominio}</h2>
      <div className="grid sm:grid-cols-2 gap-3">
        {APPS.map((a) => (
          <label key={a.id} className={`border rounded p-3 cursor-pointer ${app === a.id ? "border-ms-blue bg-ms-blue-lighter/50" : "border-ms-gray-30"}`}>
            <input type="radio" name="app" value={a.id} checked={app === a.id} onChange={() => setApp(a.id)} className="mr-2" />
            <span className="font-medium">{a.nombre}</span>
            <span className="block text-xs text-ms-gray-90 mt-1">{a.desc}</span>
          </label>
        ))}
      </div>
      <div className="grid sm:grid-cols-2 gap-3">
        <input placeholder="Nombre del sitio" maxLength={100} value={titulo} onChange={(e) => setTitulo(e.target.value)}
          className="px-3 py-2 border border-ms-gray-40 rounded text-sm focus:outline-none focus:border-ms-blue" />
        <input placeholder="Correo del administrador" type="email" value={correo} onChange={(e) => setCorreo(e.target.value)}
          className="px-3 py-2 border border-ms-gray-40 rounded text-sm focus:outline-none focus:border-ms-blue" />
      </div>
      <p className="text-xs text-ms-gray-90">Software libre (licencia GPL). Se descarga la versión oficial vigente y se verifica su integridad antes de instalarla. El sitio debe estar vacío.</p>
      <div className="flex gap-2">
        <button onClick={() => onInstalar(app, titulo.trim(), correo.trim())} disabled={ocupado || !titulo.trim() || !correo.trim()}
          className="px-4 py-2 bg-ms-blue text-white rounded text-sm disabled:opacity-50">Instalar</button>
        <button onClick={onCancelar} className="px-4 py-2 border border-ms-gray-40 rounded text-sm text-ms-gray-90">Cancelar</button>
      </div>
    </div>
  );
}
