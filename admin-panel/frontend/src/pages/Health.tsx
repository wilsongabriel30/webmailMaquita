import { useEffect, useState } from "react";
import { api } from "../api/client";

export function Health() {
  const [health, setHealth] = useState<any>(null);
  const [jails, setJails] = useState<any[]>([]);
  const [conns, setConns] = useState<any[]>([]);

  const loadAll = () => {
    api.get("/health").then(setHealth).catch(() => {});
    api.get("/health/fail2ban").then(setJails).catch(() => {});
    api.get("/health/connections").then(setConns).catch(() => {});
  };

  useEffect(() => { loadAll(); }, []);

  if (!health) return <div className="p-8 flex items-center justify-center h-full"><div className="animate-spin w-8 h-8 border-2 border-ms-blue border-t-transparent rounded-full" /></div>;

  const formatBytes = (b: number) => b > 1073741824 ? `${(b / 1073741824).toFixed(1)} GB` : `${(b / 1048576).toFixed(0)} MB`;
  const uptimeDays = Math.floor(health.uptime_seconds / 86400);
  const uptimeHours = Math.floor((health.uptime_seconds % 86400) / 3600);
  const memPercent = health.memory.total > 0 ? ((health.memory.used / health.memory.total) * 100).toFixed(1) : 0;

  return (
    <div className="p-6 space-y-5">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-ms-gray-130" title="Estado del sistema en tiempo real. Muestra CPU, memoria, discos, Fail2ban y conexiones. Solo lectura.">Estado del sistema</h1>
        <button onClick={loadAll} title="Recarga el estado del sistema. Solo lectura, no modifica nada." className="px-3 py-1.5 border border-ms-gray-40 rounded text-xs text-ms-gray-130 hover:bg-ms-gray-20">Actualizar</button>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <div className="bg-white rounded border border-ms-gray-30 p-4" title="Informacion del procesador y carga del sistema. Solo lectura.">
          <p className="text-[11px] text-ms-gray-60 font-medium uppercase">CPU</p>
          <p className="text-2xl font-bold text-ms-gray-130">{health.cpu_cores} cores</p>
          <p className="text-xs text-ms-gray-60 mt-1">Load: {health.load_avg["1m"]} / {health.load_avg["5m"]} / {health.load_avg["15m"]}</p>
        </div>
        <div className="bg-white rounded border border-ms-gray-30 p-4" title="Uso de memoria RAM del servidor. Solo lectura.">
          <p className="text-[11px] text-ms-gray-60 font-medium uppercase">Memoria</p>
          <p className="text-2xl font-bold text-ms-gray-130">{memPercent}%</p>
          <p className="text-xs text-ms-gray-60 mt-1">{formatBytes(health.memory.used)} / {formatBytes(health.memory.total)}</p>
          <div className="mt-2 w-full bg-ms-gray-30 rounded-full h-2">
            <div className={`h-2 rounded-full ${+memPercent > 80 ? "bg-ms-red" : "bg-ms-green"}`} style={{ width: `${memPercent}%` }} />
          </div>
        </div>
        <div className="bg-white rounded border border-ms-gray-30 p-4" title="Tiempo que lleva el servidor encendido sin reiniciar. Solo lectura.">
          <p className="text-[11px] text-ms-gray-60 font-medium uppercase">Uptime</p>
          <p className="text-2xl font-bold text-ms-gray-130">{uptimeDays}d {uptimeHours}h</p>
        </div>
        <div className="bg-white rounded border border-ms-gray-30 p-4" title="Numero de conexiones IMAP activas en este momento. Solo lectura.">
          <p className="text-[11px] text-ms-gray-60 font-medium uppercase">Conexiones IMAP</p>
          <p className="text-2xl font-bold text-ms-gray-130">{conns.length}</p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        <div className="bg-white rounded border border-ms-gray-30 p-5" title="Uso de espacio en disco de cada particion. Solo lectura.">
          <h2 className="text-sm font-semibold text-ms-gray-130 mb-4">Discos</h2>
          <div className="space-y-4">
            {health.disks.map((d: any, i: number) => {
              const pct = d.size > 0 ? ((d.used / d.size) * 100).toFixed(1) : 0;
              return (
                <div key={i}>
                  <div className="flex justify-between text-sm mb-1">
                    <span className="font-medium text-ms-gray-130">{d.mount}</span>
                    <span className="text-ms-gray-60 text-xs">{formatBytes(d.used)} / {formatBytes(d.size)} ({pct}%)</span>
                  </div>
                  <div className="w-full bg-ms-gray-30 rounded-full h-2.5">
                    <div className={`h-2.5 rounded-full ${+pct > 90 ? "bg-ms-red" : +pct > 70 ? "bg-ms-yellow" : "bg-ms-green"}`} style={{ width: `${pct}%` }} />
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        <div className="bg-white rounded border border-ms-gray-30 p-5" title="Estado de Fail2ban: IPs baneadas por intentos de acceso maliciosos. Solo lectura.">
          <h2 className="text-sm font-semibold text-ms-gray-130 mb-4">Fail2ban Jails</h2>
          {jails.length > 0 ? (
            <div className="space-y-2">
              {jails.map((j) => (
                <div key={j.name} className="flex items-center justify-between p-3 bg-ms-gray-10 rounded border border-ms-gray-30" title={`Jail: ${j.name}. Baneados actualmente: ${j.currently_banned}. Total historico: ${j.total_banned}. Solo lectura.`}>
                  <span className="text-sm font-medium text-ms-gray-130">{j.name}</span>
                  <div className="flex gap-2 text-xs">
                    <span className={`px-2 py-0.5 rounded ${j.currently_banned > 0 ? "bg-red-50 text-ms-red" : "bg-green-50 text-ms-green"}`}>
                      Baneados: {j.currently_banned}
                    </span>
                    <span className="text-ms-gray-60">Total: {j.total_banned}</span>
                  </div>
                </div>
              ))}
            </div>
          ) : <p className="text-ms-gray-60 text-sm">Sin datos de Fail2ban</p>}
        </div>

        <div className="bg-white rounded border border-ms-gray-30 p-5 lg:col-span-2" title="Conexiones IMAP/POP3 activas de los usuarios. Solo lectura.">
          <h2 className="text-sm font-semibold text-ms-gray-130 mb-4">Conexiones activas</h2>
          {conns.length > 0 ? (
            <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
              {conns.map((c, i) => (
                <div key={i} className="flex items-center justify-between p-2.5 bg-ms-gray-10 rounded border border-ms-gray-30 text-xs" title={`Usuario: ${c.username}. Servicio: ${c.service}. Conexiones: ${c.connections}. Solo lectura.`}>
                  <span className="font-medium text-ms-gray-130 truncate">{c.username}</span>
                  <span className="px-1.5 py-0.5 bg-ms-blue-light text-ms-blue rounded text-[10px] shrink-0 ml-1">{c.service} ({c.connections})</span>
                </div>
              ))}
            </div>
          ) : <p className="text-ms-gray-60 text-sm">Sin conexiones activas</p>}
        </div>
      </div>
    </div>
  );
}
