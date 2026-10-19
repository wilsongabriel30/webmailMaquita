import { useEffect, useMemo, useState } from "react";
import { api } from "../../api/client";

export interface AppCatalogo {
  id: string;
  nombre: string;
  descripcion: string;
  categoria: string;
  licencia: string;
  modo: "automatica" | "asistente";
  verificacion: string;
  bd: boolean;
}

/* Catálogo del servidor (lo que el ayudante sabe instalar). Se pide una vez por pantalla. */
export function useCatalogo() {
  const [apps, setApps] = useState<AppCatalogo[]>([]);
  useEffect(() => { api.get<{ aplicaciones: AppCatalogo[] }>("/sitios/catalogo").then((d) => setApps(d.aplicaciones)).catch(() => setApps([])); }, []);
  return apps;
}

/* Elegir aplicación (software libre) para un sitio vacío, como en Softaculous: por categorías y con buscador. */
export function InstalarAppForm({ dominio, apps, ocupado, onCancelar, onInstalar, onSubirPaquete }: {
  dominio: string;
  apps: AppCatalogo[];
  ocupado: boolean;
  onCancelar: () => void;
  onInstalar: (app: string, titulo: string, correo: string) => void;
  onSubirPaquete: () => void;
}) {
  const [app, setApp] = useState("wordpress");
  const [titulo, setTitulo] = useState("");
  const [correo, setCorreo] = useState("");
  const [buscar, setBuscar] = useState("");
  const [categoria, setCategoria] = useState("");

  const categorias = useMemo(() => [...new Set(apps.map((a) => a.categoria))].sort(), [apps]);
  const visibles = apps.filter((a) =>
    (!categoria || a.categoria === categoria) &&
    (!buscar || `${a.nombre} ${a.descripcion} ${a.categoria}`.toLowerCase().includes(buscar.toLowerCase())));
  const elegida = apps.find((a) => a.id === app);

  return (
    <div className="bg-white rounded border border-ms-gray-30 p-5 space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-base font-semibold text-ms-gray-130">Instalar una aplicación en {dominio}</h2>
        <button onClick={onSubirPaquete} className="text-sm text-ms-blue hover:underline">¿Tiene su propio paquete (.zip o .tar.gz)? Súbalo</button>
      </div>
      <div className="flex flex-wrap gap-2">
        <input placeholder={`Buscar entre ${apps.length} aplicaciones…`} value={buscar} onChange={(e) => setBuscar(e.target.value)}
          className="px-3 py-2 border border-ms-gray-40 rounded text-sm w-72 focus:outline-none focus:border-ms-blue" />
        <select value={categoria} onChange={(e) => setCategoria(e.target.value)} className="px-3 py-2 border border-ms-gray-40 rounded text-sm">
          <option value="">Todas las categorías</option>
          {categorias.map((c) => <option key={c}>{c}</option>)}
        </select>
      </div>
      <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3 max-h-[420px] overflow-y-auto pr-1">
        {visibles.map((a) => (
          <label key={a.id} className={`border rounded p-3 cursor-pointer ${app === a.id ? "border-ms-blue bg-ms-blue-lighter/50" : "border-ms-gray-30"}`}>
            <input type="radio" name="app" value={a.id} checked={app === a.id} onChange={() => setApp(a.id)} className="mr-2" />
            <span className="font-medium">{a.nombre}</span> <span className="text-xs text-ms-gray-60">({a.licencia})</span>
            <span className="block text-[11px] text-ms-gray-60">{a.categoria}{a.modo === "asistente" ? " · se termina en su asistente" : ""}</span>
            <span className="block text-xs text-ms-gray-90 mt-1">{a.descripcion}</span>
          </label>
        ))}
        {visibles.length === 0 && <p className="text-sm text-ms-gray-60">Ninguna aplicación coincide.</p>}
      </div>
      <div className="grid sm:grid-cols-2 gap-3">
        <input placeholder="Nombre del sitio" maxLength={100} value={titulo} onChange={(e) => setTitulo(e.target.value)}
          className="px-3 py-2 border border-ms-gray-40 rounded text-sm focus:outline-none focus:border-ms-blue" />
        <input placeholder="Correo del administrador" type="email" value={correo} onChange={(e) => setCorreo(e.target.value)}
          className="px-3 py-2 border border-ms-gray-40 rounded text-sm focus:outline-none focus:border-ms-blue" />
      </div>
      <p className="text-xs text-ms-gray-90">
        Todo es software libre, descargado de su origen oficial
        {elegida?.verificacion === "HTTPS" ? " por HTTPS (este proyecto no publica suma; se anota la del archivo instalado)"
          : elegida?.verificacion === "firma oficial" ? " y verificado con la firma del proyecto" : " y verificado con su suma publicada"}.
        {elegida?.modo === "asistente" ? " Al terminar se abre el instalador de la aplicación con los datos de su base ya preparados." : ""} El sitio debe estar vacío.
      </p>
      <div className="flex gap-2">
        <button onClick={() => onInstalar(app, titulo.trim(), correo.trim())} disabled={ocupado || !titulo.trim() || !correo.trim() || !elegida}
          className="px-4 py-2 bg-ms-blue text-white rounded text-sm disabled:opacity-50">Instalar {elegida?.nombre}</button>
        <button onClick={onCancelar} className="px-4 py-2 border border-ms-gray-40 rounded text-sm text-ms-gray-90">Cancelar</button>
      </div>
    </div>
  );
}
