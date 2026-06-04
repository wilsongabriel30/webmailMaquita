import { useEffect, useState, useCallback } from "react";
import { api } from "../api/client";

/* ── Types ── */
interface Service {
  key: string;
  label: string;
  unit: string;
  status: string;
  enabled: string;
  pid: number | null;
  memory_bytes: number | null;
  since: string;
  sub_state: string;
}

interface Jail {
  name: string;
  currently_banned: number;
  total_banned: number;
  banned_ips: string[];
}

interface SearchResult {
  ip: string;
  jails: string[];
}

interface ServiceConfig {
  service: string;
  config: Record<string, string>;
  editable_keys?: string[];
}

interface JailConfig {
  jail: string;
  bantime: string;
  maxretry: string;
  findtime: string;
}

type Tab = "servicios" | "fail2ban" | "configuración";

/* ── Helpers ── */
const formatMem = (b: number | null) => {
  if (!b) return "-";
  if (b > 1073741824) return `${(b / 1073741824).toFixed(1)} GB`;
  return `${(b / 1048576).toFixed(0)} MB`;
};

const statusColor = (s: string, subState?: string) => {
  if (subState === "exited" || subState === "dead") return "bg-yellow-500";
  if (s === "active") return "bg-ms-green";
  if (s === "inactive") return "bg-ms-gray-60";
  return "bg-ms-red";
};

/* ══════════════════════════════════════════════════════════════ */
export function Services() {
  const [tab, setTab] = useState<Tab>("servicios");

  /* ── Servicios state ── */
  const [services, setServices] = useState<Service[]>([]);
  const [logs, setLogs] = useState<{ service: string; lines: string[] } | null>(null);
  const [logLoading, setLogLoading] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  /* ── Fail2ban state ── */
  const [jails, setJails] = useState<Jail[]>([]);
  const [expandedJails, setExpandedJails] = useState<Set<string>>(new Set());
  const [searchIp, setSearchIp] = useState("");
  const [searchResult, setSearchResult] = useState<SearchResult | null>(null);
  const [searchLoading, setSearchLoading] = useState(false);
  const [banIp, setBanIp] = useState("");
  const [banJail, setBanJail] = useState("");
  const [banLoading, setBanLoading] = useState(false);
  const [unbanAllIp, setUnbanAllIp] = useState("");
  const [unbanAllLoading, setUnbanAllLoading] = useState(false);
  const [f2bActionLoading, setF2bActionLoading] = useState<string | null>(null);

  /* ── Config state ── */
  const [configService, setConfigService] = useState("");
  const [serviceConfig, setServiceConfig] = useState<ServiceConfig | null>(null);
  const [configLoading, setConfigLoading] = useState(false);
  const [configEdits, setConfigEdits] = useState<Record<string, string>>({});
  const [configSaving, setConfigSaving] = useState(false);
  const [jailConfigs, setJailConfigs] = useState<JailConfig[]>([]);
  const [jailConfigEdits, setJailConfigEdits] = useState<Record<string, Record<string, string>>>({});
  const [jailConfigSaving, setJailConfigSaving] = useState<string | null>(null);

  /* ── Auth confirm for dangerous actions ── */
  const [authModal, setAuthModal] = useState<{ action: () => Promise<void>; message: string } | null>(null);
  const [authPassword, setAuthPassword] = useState("");
  const [authError, setAuthError] = useState("");

  const requireAuth = (message: string, action: () => Promise<void>) => {
    setAuthModal({ action, message });
    setAuthPassword("");
    setAuthError("");
  };

  const confirmAuth = async () => {
    if (!authPassword) { setAuthError("Ingrese su contraseña"); return; }
    try {
      await api.post("/auth/verify-password", { password: authPassword });
      const action = authModal?.action;
      setAuthModal(null);
      setAuthPassword("");
      setAuthError("");
      if (action) await action();
    } catch {
      setAuthError("Contraseña incorrecta. Solo administradores autorizados pueden editar configuraciónes.");
    }
  };

  /* ── Data loading ── */
  const loadServices = useCallback(() => {
    api.get<Service[]>("/services").then(setServices).catch(() => {});
  }, []);

  const loadJails = useCallback(() => {
    api.get<Jail[]>("/services/fail2ban/jails").then(setJails).catch(() => {});
  }, []);

  useEffect(() => {
    loadServices();
    loadJails();
  }, [loadServices, loadJails]);

  /* ── Service actions ── */
  const doAction = async (key: string, action: string) => {
    if (action === "stop" && !confirm(`PRECAUCION: Detener ${key} interrumpira el servicio de correo. Solo detener si es absolutamente necesario. Esta accion se registra en auditoria.\n\nDesea continuar?`)) return;
    if (action === "restart" && !confirm(`Reiniciar ${key}? Los correos en proceso pueden retrasarse. Se registra en auditoria.\n\nDesea continuar?`)) return;
    setActionLoading(`${key}-${action}`);
    try {
      const res: any = await api.post(`/services/${key}/${action}`);
      if (!res.ok) alert(`Error: ${res.error}`);
      setTimeout(loadServices, 1500);
    } catch (e: any) {
      alert(e.message);
    }
    setActionLoading(null);
  };

  const showLogs = async (key: string) => {
    setLogLoading(key);
    try {
      const res = await api.get<{ service: string; lines: string[] }>(`/services/${key}/logs?lines=80`);
      setLogs(res);
    } catch {}
    setLogLoading(null);
  };

  /* ── Fail2ban actions ── */
  const searchIpAction = async () => {
    if (!searchIp.trim()) return;
    setSearchLoading(true);
    setSearchResult(null);
    try {
      const res = await api.get<SearchResult>(`/services/fail2ban/search/${encodeURIComponent(searchIp.trim())}`);
      setSearchResult(res);
    } catch {
      // If endpoint not available, do manual search across jails
      const found: string[] = [];
      for (const j of jails) {
        if (j.banned_ips.includes(searchIp.trim())) found.push(j.name);
      }
      setSearchResult({ ip: searchIp.trim(), jails: found });
    }
    setSearchLoading(false);
  };

  const banIpAction = async () => {
    if (!banIp.trim() || !banJail) return;
    const targetLabel = banJail === "__ALL__" ? "TODOS los jails" : `el jail ${banJail}`;
    if (!confirm(`PRECAUCION: Va a banear la IP ${banIp.trim()} en ${targetLabel}.\n\nAsegurese de que NO es una IP de un usuario legitimo. Esta accion bloqueara todas las conexiones desde esa IP.\n\nSe registra en auditoria.\n\nDesea continuar?`)) return;
    setBanLoading(true);
    try {
      if (banJail === "__ALL__") {
        for (const j of jails) {
          await api.post("/services/fail2ban/ban", { jail: j.name, ip: banIp.trim() });
        }
      } else {
        const res: any = await api.post("/services/fail2ban/ban", { jail: banJail, ip: banIp.trim() });
        if (!res.ok) alert(`Error: ${res.error}`);
      }
      setBanIp("");
      setBanJail("");
      loadJails();
    } catch (e: any) {
      alert(e.message);
    }
    setBanLoading(false);
  };

  const unbanFromAll = async (ip: string) => {
    if (!confirm(`ATENCION: Va a desbanear ${ip} de TODOS los jails.\n\nVerifique que esta IP no sea de un atacante activo antes de desbanear. Si es un atacante, volvera a intentar conexiones inmediatamente.\n\nSe registra en auditoria.\n\nDesea continuar?`)) return;
    setF2bActionLoading(ip);
    try {
      await api.post("/services/fail2ban/unban-all", { ip });
    } catch {
      // Fallback: unban from each jail individually
      for (const j of jails) {
        if (j.banned_ips.includes(ip)) {
          await api.post("/services/fail2ban/unban", { jail: j.name, ip }).catch(() => {});
        }
      }
    }
    loadJails();
    setF2bActionLoading(null);
  };

  const unbanFromJail = async (jail: string, ip: string) => {
    if (!confirm(`Desbanear ${ip} de ${jail}?\n\nVerifique que no sea un atacante antes de desbanear. Se registra en auditoria.`)) return;
    setF2bActionLoading(`${jail}-${ip}`);
    try {
      await api.post("/services/fail2ban/unban", { jail, ip });
      loadJails();
    } catch (e: any) {
      alert(e.message);
    }
    setF2bActionLoading(null);
  };

  const unbanAllFromEverywhere = async () => {
    if (!unbanAllIp.trim()) return;
    if (!confirm(`ATENCION: Va a desbanear ${unbanAllIp.trim()} de TODOS los jails.\n\nVerifique que esta IP no sea de un atacante activo antes de desbanear. Si es un atacante, volvera a intentar conexiones inmediatamente.\n\nSe registra en auditoria.\n\nDesea continuar?`)) return;
    setUnbanAllLoading(true);
    try {
      await api.post("/services/fail2ban/unban-all", { ip: unbanAllIp.trim() });
    } catch {
      for (const j of jails) {
        if (j.banned_ips.includes(unbanAllIp.trim())) {
          await api.post("/services/fail2ban/unban", { jail: j.name, ip: unbanAllIp.trim() }).catch(() => {});
        }
      }
    }
    setUnbanAllIp("");
    loadJails();
    setUnbanAllLoading(false);
  };

  const toggleJail = (name: string) => {
    setExpandedJails((prev) => {
      const next = new Set(prev);
      if (next.has(name)) next.delete(name);
      else next.add(name);
      return next;
    });
  };

  /* ── Config actions ── */
  const loadConfig = async (key: string) => {
    if (!key) {
      setServiceConfig(null);
      setJailConfigs([]);
      return;
    }
    setConfigLoading(true);
    setServiceConfig(null);
    setJailConfigs([]);
    setConfigEdits({});
    setJailConfigEdits({});
    try {
      if (key === "fail2ban") {
        const res: any = await api.get(`/services/${key}/config`);
        const jailsArr = res.jails || res;
        const mapped = (Array.isArray(jailsArr) ? jailsArr : []).map((j: any) => ({
          jail: j.name || j.jail,
          bantime: String(j.config?.bantime ?? j.bantime ?? ""),
          maxretry: String(j.config?.maxretry ?? j.maxretry ?? ""),
          findtime: String(j.config?.findtime ?? j.findtime ?? ""),
        }));
        setJailConfigs(mapped);
      } else {
        const res = await api.get<ServiceConfig>(`/services/${key}/config`);
        setServiceConfig(res);
        if (res.config) {
          setConfigEdits({ ...res.config });
        }
      }
    } catch (e: any) {
      alert(`Error cargando config: ${e.message}`);
    }
    setConfigLoading(false);
  };

  const saveConfig = async () => {
    if (!configService || !serviceConfig) return;
    const changed: Record<string, string> = {};
    if (serviceConfig.editable_keys) {
      for (const k of serviceConfig.editable_keys) {
        if (configEdits[k] !== undefined && configEdits[k] !== serviceConfig.config[k]) {
          changed[k] = configEdits[k];
        }
      }
    }
    if (Object.keys(changed).length === 0) { alert("No hay cambios para guardar"); return; }
    requireAuth(
      `Va a guardar cambios de configuración para ${configService}. Esto recargara el servicio automaticamente. Se registra en auditoria.`,
      async () => {
        setConfigSaving(true);
        try {
          await api.put(`/services/${configService}/config`, changed);
          alert("Configuracion guardada y servicio recargado");
          loadConfig(configService);
        } catch (e: any) {
          alert(`Error: ${e.message}`);
        }
        setConfigSaving(false);
      }
    );
  };

  const saveJailConfig = async (jail: string) => {
    const edits = jailConfigEdits[jail] || {};
    if (Object.keys(edits).length === 0) { alert("No hay cambios"); return; }
    requireAuth(
      `Va a guardar cambios de configuración para el jail ${jail}. Se aplican inmediatamente. Se registra en auditoria.`,
      async () => {
        setJailConfigSaving(jail);
        try {
          await api.put(`/services/fail2ban/jail-config/${jail}`, edits);
          alert(`Config de ${jail} guardada`);
          loadConfig("fail2ban");
        } catch (e: any) {
          alert(`Error: ${e.message}`);
        }
        setJailConfigSaving(null);
      }
    );
  };

  /* ── Tab button styles ── */
  const tabCls = (t: Tab) =>
    `px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
      tab === t
        ? "border-ms-blue text-ms-blue"
        : "border-transparent text-ms-gray-90 hover:text-ms-gray-130 hover:border-ms-gray-40"
    }`;

  /* ══════════════════════════════════════════════════════════════ */
  return (
    <div className="p-6 space-y-5">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-ms-gray-130">Gestión de Servicios</h1>
        <button
          onClick={() => { loadServices(); loadJails(); }}
          className="px-3 py-1.5 text-xs border border-ms-gray-40 rounded hover:bg-ms-gray-20 text-ms-gray-130"
          title="Actualiza la lista de servicios y el estado de Fail2ban. No modifica nada, solo lectura."
        >
          Actualizar
        </button>
      </div>

      {/* Tabs */}
      <div className="flex border-b border-ms-gray-30">
        <button className={tabCls("servicios")} onClick={() => setTab("servicios")} title="Ver y gestionar los servicios del servidor de correo (iniciar, detener, reiniciar, ver logs).">Servicios</button>
        <button className={tabCls("fail2ban")} onClick={() => setTab("fail2ban")} title="Gestionar Fail2ban: buscar, banear y desbanear IPs. Precaucion al desbanear IPs de atacantes.">Fail2ban</button>
        <button className={tabCls("configuración")} onClick={() => setTab("configuración")} title="Editar la configuración de los servicios. Los cambios se aplican al guardar y se registran en auditoria.">Configuracion</button>
      </div>

      {/* ══════════════ TAB: SERVICIOS ══════════════ */}
      {tab === "servicios" && (
        <div className="space-y-5">
          {/* Services grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {services.map((svc) => (
              <div key={svc.key} className="bg-white rounded border border-ms-gray-30 p-4">
                <div className="flex items-start justify-between mb-3">
                  <div className="flex items-center gap-2">
                    <span className={`w-2.5 h-2.5 rounded-full ${statusColor(svc.status, svc.sub_state)}`} />
                    <div>
                      <h3 className="text-sm font-semibold text-ms-gray-130">{svc.label}</h3>
                      <span className="text-[10px] text-ms-gray-60">{svc.unit}</span>
                    </div>
                  </div>
                  <div className="flex items-center gap-1">
                    <span
                      className={`text-[10px] px-1.5 py-0.5 rounded ${
                        svc.sub_state === "exited" || svc.sub_state === "dead" ? "bg-yellow-50 text-yellow-700" :
                        svc.status === "active" ? "bg-green-50 text-ms-green" : "bg-red-50 text-ms-red"
                      }`}
                    >
                      {svc.sub_state === "exited" ? "exited" : svc.sub_state === "dead" ? "dead" : svc.status}
                    </span>
                    <span className="text-[10px] px-1.5 py-0.5 rounded bg-ms-gray-20 text-ms-gray-90">
                      {svc.enabled}
                    </span>
                  </div>
                </div>

                <div className="grid grid-cols-3 gap-2 mb-3 text-[11px]">
                  <div>
                    <span className="text-ms-gray-60">PID</span>
                    <p className="font-medium text-ms-gray-130">{svc.pid || "-"}</p>
                  </div>
                  <div>
                    <span className="text-ms-gray-60">Memoria</span>
                    <p className="font-medium text-ms-gray-130">{formatMem(svc.memory_bytes)}</p>
                  </div>
                  <div>
                    <span className="text-ms-gray-60">Estado</span>
                    <p className="font-medium text-ms-gray-130">{svc.sub_state || "-"}</p>
                  </div>
                </div>

                <div className="flex gap-1.5">
                  {svc.status === "active" ? (
                    <>
                      <button
                        onClick={() => doAction(svc.key, "restart")}
                        disabled={actionLoading === `${svc.key}-restart`}
                        className="px-2.5 py-1 text-[11px] bg-ms-blue text-white rounded hover:bg-ms-blue-dark disabled:opacity-50"
                        title="Reinicia el servicio. Los correos en proceso pueden retrasarse. Se registra en auditoria."
                      >
                        {actionLoading === `${svc.key}-restart` ? "..." : "Reiniciar"}
                      </button>
                      <button
                        onClick={() => doAction(svc.key, "stop")}
                        disabled={actionLoading === `${svc.key}-stop`}
                        className="px-2.5 py-1 text-[11px] border border-ms-red text-ms-red rounded hover:bg-red-50 disabled:opacity-50"
                        title="PRECAUCION: Detener este servicio interrumpira el correo. Solo detener si es absolutamente necesario. No detener en horario laboral salvo emergencia. Se registra en auditoria."
                      >
                        Detener
                      </button>
                    </>
                  ) : (
                    <button
                      onClick={() => doAction(svc.key, "start")}
                      disabled={actionLoading === `${svc.key}-start`}
                      className="px-2.5 py-1 text-[11px] bg-ms-green text-white rounded hover:bg-green-700 disabled:opacity-50"
                      title="Inicia el servicio si esta detenido. Se registra en auditoria."
                    >
                      {actionLoading === `${svc.key}-start` ? "..." : "Iniciar"}
                    </button>
                  )}
                  <button
                    onClick={() => doAction(svc.key, "reload")}
                    className="px-2.5 py-1 text-[11px] border border-ms-gray-40 text-ms-gray-90 rounded hover:bg-ms-gray-20"
                    title="Recarga la configuración sin detener el servicio. Mas seguro que reiniciar. Se registra en auditoria."
                  >
                    Reload
                  </button>
                  <button
                    onClick={() => showLogs(svc.key)}
                    className="px-2.5 py-1 text-[11px] border border-ms-gray-40 text-ms-gray-90 rounded hover:bg-ms-gray-20 ml-auto"
                    title="Muestra las ultimas lineas del log del servicio. No modifica nada, solo lectura."
                  >
                    {logLoading === svc.key ? "..." : "Ver logs"}
                  </button>
                </div>
              </div>
            ))}
          </div>

          {/* Log viewer */}
          {logs && (
            <div className="bg-white rounded border border-ms-gray-30">
              <div className="flex items-center justify-between px-4 py-2.5 border-b border-ms-gray-30 bg-ms-gray-10">
                <span className="text-sm font-semibold text-ms-gray-130">Logs: {logs.service}</span>
                <button
                  onClick={() => setLogs(null)}
                  className="text-ms-gray-60 hover:text-ms-gray-130 text-xs"
                  title="Cierra el visor de logs. No modifica nada."
                >
                  Cerrar
                </button>
              </div>
              <div className="p-3 max-h-80 overflow-auto bg-ms-gray-150 rounded-b">
                <pre className="text-[11px] text-green-400 font-mono whitespace-pre-wrap leading-relaxed">
                  {logs.lines.join("\n")}
                </pre>
              </div>
            </div>
          )}
        </div>
      )}

      {/* ══════════════ TAB: FAIL2BAN ══════════════ */}
      {tab === "fail2ban" && (
        <div className="space-y-5">
          {/* Search IP */}
          <div className="bg-white rounded border border-ms-gray-30 p-4">
            <h2 className="text-sm font-semibold text-ms-gray-130 mb-3">Buscar IP</h2>
            <div className="flex gap-2 items-end">
              <div className="flex-1">
                <label className="text-[11px] text-ms-gray-60 block mb-1">Dirección IP</label>
                <input
                  type="text"
                  value={searchIp}
                  onChange={(e) => setSearchIp(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && searchIpAction()}
                  placeholder="Ej: 192.168.1.100"
                  className="w-full px-3 py-1.5 text-sm border border-ms-gray-40 rounded focus:outline-none focus:border-ms-blue"
                  title="Ingrese la IP a buscar en todos los jails de Fail2ban."
                />
              </div>
              <button
                onClick={searchIpAction}
                disabled={searchLoading || !searchIp.trim()}
                className="px-4 py-1.5 text-sm bg-ms-blue text-white rounded hover:bg-ms-blue-dark disabled:opacity-50"
                title="Busca si la IP esta baneada en algun jail. No modifica nada, solo lectura."
              >
                {searchLoading ? "..." : "Buscar"}
              </button>
            </div>
            {searchResult && (
              <div className="mt-3 p-3 bg-ms-gray-10 rounded border border-ms-gray-30">
                <p className="text-sm text-ms-gray-130">
                  <span className="font-mono font-semibold">{searchResult.ip}</span>
                  {searchResult.jails.length === 0 ? (
                    <span className="ml-2 text-ms-green">No esta baneada en ningun jail</span>
                  ) : (
                    <span className="ml-2 text-ms-red">
                      Baneada en: {searchResult.jails.join(", ")}
                    </span>
                  )}
                </p>
                {searchResult.jails.length > 0 && (
                  <button
                    onClick={() => unbanFromAll(searchResult.ip)}
                    disabled={f2bActionLoading === searchResult.ip}
                    className="mt-2 px-3 py-1 text-[11px] bg-ms-red text-white rounded hover:bg-red-700 disabled:opacity-50"
                    title="ATENCION: Desbanea esta IP de TODOS los jails a la vez. Verificar que no sea un atacante activo antes de desbanear. Si es un atacante, volvera a intentar conexiones inmediatamente. Se registra en auditoria."
                  >
                    {f2bActionLoading === searchResult.ip ? "..." : "Desbanear de todo"}
                  </button>
                )}
              </div>
            )}
          </div>

          {/* Ban IP + Unban All */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {/* Ban IP */}
            <div className="bg-white rounded border border-ms-gray-30 p-4">
              <h2 className="text-sm font-semibold text-ms-gray-130 mb-3">Banear IP</h2>
              <div className="space-y-2">
                <div>
                  <label className="text-[11px] text-ms-gray-60 block mb-1">Dirección IP</label>
                  <input
                    type="text"
                    value={banIp}
                    onChange={(e) => setBanIp(e.target.value)}
                    placeholder="Ej: 10.0.0.50"
                    className="w-full px-3 py-1.5 text-sm border border-ms-gray-40 rounded focus:outline-none focus:border-ms-blue"
                    title="Ingrese la IP que desea banear. Asegurese de que NO es una IP de un usuario legitimo."
                  />
                </div>
                <div>
                  <label className="text-[11px] text-ms-gray-60 block mb-1">Jail</label>
                  <select
                    value={banJail}
                    onChange={(e) => setBanJail(e.target.value)}
                    className="w-full px-3 py-1.5 text-sm border border-ms-gray-40 rounded focus:outline-none focus:border-ms-blue bg-white"
                    title="Seleccione en que jail banear la IP. 'Todos los jails' la bloqueara en todos los servicios protegidos."
                  >
                    <option value="">Seleccionar jail...</option>
                    <option value="__ALL__">Todos los jails</option>
                    {jails.map((j) => (
                      <option key={j.name} value={j.name}>{j.name}</option>
                    ))}
                  </select>
                </div>
                <button
                  onClick={banIpAction}
                  disabled={banLoading || !banIp.trim() || !banJail}
                  className="px-4 py-1.5 text-sm bg-ms-red text-white rounded hover:bg-red-700 disabled:opacity-50"
                  title="PRECAUCION: Bloquea esta IP impidiendo conexiones. Asegurese de no banear IPs de usuarios legitimos. Si selecciono 'Todos los jails', la IP quedara bloqueada en todos los servicios. Se registra en auditoria."
                >
                  {banLoading ? "Baneando..." : "Banear"}
                </button>
              </div>
            </div>

            {/* Unban from all */}
            <div className="bg-white rounded border border-ms-gray-30 p-4">
              <h2 className="text-sm font-semibold text-ms-gray-130 mb-3">Desbanear IP de todos los jails</h2>
              <div className="space-y-2">
                <div>
                  <label className="text-[11px] text-ms-gray-60 block mb-1">Dirección IP</label>
                  <input
                    type="text"
                    value={unbanAllIp}
                    onChange={(e) => setUnbanAllIp(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && unbanAllFromEverywhere()}
                    placeholder="Ej: 10.0.0.50"
                    className="w-full px-3 py-1.5 text-sm border border-ms-gray-40 rounded focus:outline-none focus:border-ms-blue"
                    title="Ingrese la IP que desea desbanear de todos los jails. Verificar primero que no sea un atacante."
                  />
                </div>
                <button
                  onClick={unbanAllFromEverywhere}
                  disabled={unbanAllLoading || !unbanAllIp.trim()}
                  className="px-4 py-1.5 text-sm bg-ms-blue text-white rounded hover:bg-ms-blue-dark disabled:opacity-50"
                  title="ATENCION: Desbanea esta IP de TODOS los jails a la vez. Verificar que no sea un atacante activo antes de desbanear. Si es un atacante, volvera a intentar conexiones inmediatamente. Se registra en auditoria."
                >
                  {unbanAllLoading ? "Desbaneando..." : "Desbanear de todo"}
                </button>
              </div>
            </div>
          </div>

          {/* Jail cards */}
          <div className="space-y-3">
            <h2 className="text-sm font-semibold text-ms-gray-130">Jails ({jails.length})</h2>
            {jails.length === 0 ? (
              <p className="text-ms-gray-60 text-sm">Sin datos de Fail2ban</p>
            ) : (
              jails.map((j) => (
                <div key={j.name} className="bg-white rounded border border-ms-gray-30">
                  {/* Jail header - clickable */}
                  <button
                    onClick={() => toggleJail(j.name)}
                    className="w-full flex items-center justify-between px-4 py-3 text-left hover:bg-ms-gray-10 transition-colors"
                    title={`Expandir/colapsar el jail ${j.name} para ver las IPs baneadas. No modifica nada.`}
                  >
                    <div className="flex items-center gap-3">
                      <svg
                        className={`w-3 h-3 text-ms-gray-60 transition-transform ${expandedJails.has(j.name) ? "rotate-90" : ""}`}
                        fill="currentColor"
                        viewBox="0 0 20 20"
                      >
                        <path
                          fillRule="evenodd"
                          d="M7.21 14.77a.75.75 0 01.02-1.06L11.168 10 7.23 6.29a.75.75 0 111.04-1.08l4.5 4.25a.75.75 0 010 1.08l-4.5 4.25a.75.75 0 01-1.06-.02z"
                          clipRule="evenodd"
                        />
                      </svg>
                      <span className="text-sm font-semibold text-ms-gray-130">{j.name}</span>
                    </div>
                    <div className="flex gap-3 text-[11px]">
                      <span
                        className={`px-2 py-0.5 rounded ${
                          j.currently_banned > 0 ? "bg-red-50 text-ms-red font-medium" : "bg-green-50 text-ms-green"
                        }`}
                      >
                        Baneados: {j.currently_banned}
                      </span>
                      <span className="text-ms-gray-60">Total historico: {j.total_banned}</span>
                    </div>
                  </button>

                  {/* Jail body - expanded */}
                  {expandedJails.has(j.name) && (
                    <div className="px-4 pb-4 border-t border-ms-gray-30">
                      {j.banned_ips.length === 0 ? (
                        <p className="text-ms-gray-60 text-xs mt-3">Sin IPs baneadas actualmente</p>
                      ) : (
                        <div className="mt-3 space-y-1.5">
                          {j.banned_ips.map((ip) => (
                            <div
                              key={ip}
                              className="flex items-center justify-between px-3 py-1.5 bg-red-50 border border-ms-red/20 rounded"
                            >
                              <span className="font-mono text-xs text-ms-red">{ip}</span>
                              <div className="flex gap-1.5">
                                <button
                                  onClick={() => unbanFromJail(j.name, ip)}
                                  disabled={f2bActionLoading === `${j.name}-${ip}`}
                                  className="px-2 py-0.5 text-[10px] border border-ms-gray-40 text-ms-gray-90 rounded hover:bg-white disabled:opacity-50"
                                  title={`Desbanea esta IP solo del jail ${j.name}. Verificar que no sea un atacante antes de desbanear. Se registra en auditoria.`}
                                >
                                  {f2bActionLoading === `${j.name}-${ip}` ? "..." : "Desbanear"}
                                </button>
                                <button
                                  onClick={() => unbanFromAll(ip)}
                                  disabled={f2bActionLoading === ip}
                                  className="px-2 py-0.5 text-[10px] bg-ms-red text-white rounded hover:bg-red-700 disabled:opacity-50"
                                  title="ATENCION: Desbanea esta IP de TODOS los jails a la vez. Verificar que no sea un atacante activo antes de desbanear. Si es un atacante, volvera a intentar conexiones inmediatamente. Se registra en auditoria."
                                >
                                  {f2bActionLoading === ip ? "..." : "Desbanear de todo"}
                                </button>
                              </div>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              ))
            )}
          </div>
        </div>
      )}

      {/* ══════════════ TAB: CONFIGURACION ══════════════ */}
      {tab === "configuración" && (
        <div className="space-y-5">
          {/* Service selector */}
          <div className="bg-white rounded border border-ms-gray-30 p-4">
            <label className="text-sm font-semibold text-ms-gray-130 block mb-2">Seleccionar servicio</label>
            <select
              value={configService}
              onChange={(e) => {
                setConfigService(e.target.value);
                loadConfig(e.target.value);
              }}
              className="w-full max-w-sm px-3 py-1.5 text-sm border border-ms-gray-40 rounded focus:outline-none focus:border-ms-blue bg-white"
              title="Seleccione el servicio cuya configuración desea ver o editar. Solo seleccionar no modifica nada."
            >
              <option value="">Seleccionar...</option>
              {services.map((s) => (
                <option key={s.key} value={s.key}>{s.label}</option>
              ))}
            </select>
          </div>

          {configLoading && (
            <div className="bg-white rounded border border-ms-gray-30 p-8 text-center">
              <p className="text-sm text-ms-gray-60">Cargando configuración...</p>
            </div>
          )}

          {/* Service config (non-fail2ban) */}
          {serviceConfig && !configLoading && (
            <div className="bg-white rounded border border-ms-gray-30">
              <div className="px-4 py-3 border-b border-ms-gray-30 bg-ms-gray-10 flex items-center justify-between">
                <h2 className="text-sm font-semibold text-ms-gray-130">
                  Configuracion: {services.find((s) => s.key === configService)?.label || configService}
                </h2>
                {serviceConfig.editable_keys && serviceConfig.editable_keys.length > 0 && (
                  <button
                    onClick={saveConfig}
                    disabled={configSaving}
                    className="px-4 py-1.5 text-xs bg-ms-blue text-white rounded hover:bg-ms-blue-dark disabled:opacity-50"
                    title="PRECAUCION: Guarda los cambios de configuración y recarga el servicio automaticamente. Los correos en proceso podrian verse afectados. Los cambios se registran en auditoria para poder revertirlos."
                  >
                    {configSaving ? "Guardando..." : "Guardar cambios"}
                  </button>
                )}
              </div>
              <div className="p-4">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-ms-gray-30">
                      <th className="text-left py-2 px-3 text-[11px] font-semibold text-ms-gray-60 uppercase tracking-wide">
                        Parametro
                      </th>
                      <th className="text-left py-2 px-3 text-[11px] font-semibold text-ms-gray-60 uppercase tracking-wide">
                        Valor
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {Object.entries(serviceConfig.config).map(([key, value]) => {
                      const editable = serviceConfig.editable_keys?.includes(key);
                      return (
                        <tr key={key} className="border-b border-ms-gray-20 hover:bg-ms-gray-10">
                          <td className="py-2 px-3 font-mono text-xs text-ms-gray-130">{key}</td>
                          <td className="py-2 px-3">
                            {editable ? (
                              <input
                                type="text"
                                value={configEdits[key] ?? value}
                                onChange={(e) =>
                                  setConfigEdits((prev) => ({ ...prev, [key]: e.target.value }))
                                }
                                className="w-full px-2 py-1 text-xs font-mono border border-ms-gray-40 rounded focus:outline-none focus:border-ms-blue"
                                title={`Editar el valor de ${key}. Los cambios no se aplican hasta presionar 'Guardar cambios'.`}
                              />
                            ) : (
                              <span className="text-xs font-mono text-ms-gray-90">{value}</span>
                            )}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Fail2ban jail configs */}
          {configService === "fail2ban" && jailConfigs.length > 0 && !configLoading && (
            <div className="space-y-3">
              {jailConfigs.map((jc) => (
                <div key={jc.jail} className="bg-white rounded border border-ms-gray-30">
                  <div className="px-4 py-3 border-b border-ms-gray-30 bg-ms-gray-10 flex items-center justify-between">
                    <h3 className="text-sm font-semibold text-ms-gray-130">{jc.jail}</h3>
                    <button
                      onClick={() => saveJailConfig(jc.jail)}
                      disabled={jailConfigSaving === jc.jail}
                      className="px-3 py-1 text-xs bg-ms-blue text-white rounded hover:bg-ms-blue-dark disabled:opacity-50"
                      title={`Guarda los cambios de configuración del jail ${jc.jail} y los aplica inmediatamente. Los cambios se registran en auditoria para poder revertirlos. Valores incorrectos pueden bloquear IPs legitimas o dejar pasar atacantes.`}
                    >
                      {jailConfigSaving === jc.jail ? "..." : "Guardar"}
                    </button>
                  </div>
                  <div className="p-4 grid grid-cols-1 md:grid-cols-3 gap-3">
                    {(["bantime", "maxretry", "findtime"] as const).map((field) => (
                      <div key={field}>
                        <label className="text-[11px] text-ms-gray-60 block mb-1">{field}</label>
                        <input
                          type="text"
                          value={jailConfigEdits[jc.jail]?.[field] ?? jc[field]}
                          onChange={(e) =>
                            setJailConfigEdits((prev) => ({
                              ...prev,
                              [jc.jail]: { ...(prev[jc.jail] || {}), [field]: e.target.value },
                            }))
                          }
                          className="w-full px-3 py-1.5 text-sm font-mono border border-ms-gray-40 rounded focus:outline-none focus:border-ms-blue"
                          title={
                            field === "bantime"
                              ? "Tiempo de baneo en segundos (o formato como 1h, 1d). Valores muy bajos permiten ataques repetidos; valores muy altos pueden afectar usuarios legitimos."
                              : field === "maxretry"
                              ? "Numero maximo de intentos fallidos antes de banear. Valores muy bajos pueden banear usuarios legitimos; valores muy altos dan mas oportunidades a atacantes."
                              : "Ventana de tiempo en segundos para contar intentos fallidos. Valores muy bajos pueden dejar pasar ataques lentos."
                          }
                        />
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Empty state for config */}
          {configService && !configLoading && !serviceConfig && jailConfigs.length === 0 && (
            <div className="bg-white rounded border border-ms-gray-30 p-8 text-center">
              <p className="text-sm text-ms-gray-60">
                No se pudo cargar la configuración para este servicio.
                <br />
                <span className="text-xs">El endpoint de configuración puede no estar disponible aun.</span>
              </p>
            </div>
          )}
        </div>
      )}

      {/* Auth confirmation modal */}
      {authModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg border border-ms-gray-30 shadow-xl w-full max-w-md p-6 space-y-4">
            <div className="flex items-center gap-2">
              <svg className="w-6 h-6 text-ms-orange" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
              </svg>
              <h3 className="text-sm font-bold text-ms-gray-130">Autenticacion requerida</h3>
            </div>
            <p className="text-xs text-ms-gray-90">{authModal.message}</p>
            <div className="bg-yellow-50 border border-yellow-200 rounded p-2 text-[11px] text-yellow-800">
              Para editar configuraciónes del servidor se requiere confirmar su identidad. Ingrese su contraseña de administrador.
            </div>
            <input
              type="password"
              value={authPassword}
              onChange={(e) => { setAuthPassword(e.target.value); setAuthError(""); }}
              onKeyDown={(e) => e.key === "Enter" && confirmAuth()}
              placeholder="Contraseña de administrador"
              className="w-full px-3 py-2 border border-ms-gray-40 rounded text-sm focus:outline-none focus:border-ms-blue"
              autoFocus
            />
            {authError && <p className="text-xs text-ms-red">{authError}</p>}
            <div className="flex gap-2 justify-end">
              <button onClick={() => setAuthModal(null)} className="px-4 py-2 border border-ms-gray-40 rounded text-sm text-ms-gray-90">Cancelar</button>
              <button onClick={confirmAuth} className="px-4 py-2 bg-ms-blue text-white rounded text-sm hover:bg-ms-blue-dark">Confirmar</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
