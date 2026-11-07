const BASE = "/api";
import { reportarFallo, reportarExito } from "../lib/conexion";   // T-35: estado real de conexión
import { inicioPeticion, finPeticion, tiempoServidor, type Medida } from "../lib/conexionLenta";

// Error logger for traceability
function logError(context: string, details: Record<string, unknown>) {
  const entry = {
    ts: new Date().toISOString(),
    context,
    ...details,
  };
  console.error("[correo]", context, details);
  // Store last 50 errors in sessionStorage for debugging
  try {
    const logs = JSON.parse(sessionStorage.getItem("maquita_errors") || "[]");
    logs.push(entry);
    if (logs.length > 50) logs.shift();
    sessionStorage.setItem("maquita_errors", JSON.stringify(logs));
  } catch { /* ignore */ }
}

let isRefreshing = false;
// 05/11/2026: el refresco distingue «vencida» (el servidor dijo que no) de «temporal» (sin red,
// 5xx o 429: el servidor se está reiniciando o no responde). Antes cualquier fallo del refresco
// mandaba al login: cada reinicio del backend expulsaba a quien justo necesitaba refrescar.
type Refresco = "ok" | "vencida" | "temporal";
let refreshPromise: Promise<Refresco> | null = null;

async function tryRefresh(): Promise<Refresco> {
  if (isRefreshing && refreshPromise) return refreshPromise;
  isRefreshing = true;
  refreshPromise = fetch(`${BASE}/auth/refresh`, {
    method: "POST",
    credentials: "include",
  })
    .then((res): Promise<Refresco> | Refresco => {
      if (res.status === 401 || res.status === 403) return "vencida";
      if (!res.ok) return "temporal";
      return res.json().then((data: { refreshed?: boolean }) => (data.refreshed !== false ? "ok" : "vencida"))
        .catch((): Refresco => "temporal");
    })
    .catch((): Refresco => "temporal")
    .finally(() => {
      isRefreshing = false;
      refreshPromise = null;
    });
  return refreshPromise;
}

/** Refresca y, si el fallo es temporal (reinicio del servidor), insiste unos segundos antes de rendirse. */
async function refrescarConPaciencia(): Promise<Refresco> {
  const esperas = [1500, 2500, 4000];   // ≈ 8 s en total: lo que tarda en arrancar el backend
  let r = await tryRefresh();
  for (const ms of esperas) {
    if (r !== "temporal") break;
    await sleep(ms);
    r = await tryRefresh();
  }
  return r;
}
export const ERROR_SERVIDOR_REINICIANDO = "El servidor se está reiniciando. Inténtalo de nuevo en unos segundos.";

// Máxima espera (s) que aceptamos para reintentar automáticamente tras un 429
const MAX_RETRY_AFTER_S = 15;
const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

// Aviso de conexión lenta: se mide cada petición de principio a fin (cuerpo incluido)
async function request<T>(path: string, options: RequestInit & { skipAuth?: boolean } = {}): Promise<T> {
  const medida = inicioPeticion(path);
  try { return await requestMedido<T>(path, options, medida); } finally { finPeticion(medida); }
}

async function requestMedido<T>(path: string, options: RequestInit & { skipAuth?: boolean }, medida: Medida): Promise<T> {
  const { skipAuth, ...fetchOptions } = options;

  // Never intercept 401 on auth endpoints (login, refresh, logout)
  const isAuthEndpoint = path.startsWith("/auth/");

  let res: Response;
  try {
    res = await fetch(`${BASE}${path}`, {
      credentials: "include",
      headers: {
        "Content-Type": "application/json",
        ...fetchOptions.headers,
      },
      ...fetchOptions,
    });
  } catch (e) {
    // Cancelar a propósito (AbortController) no es «sin red»: no se avisa de conexión lenta.
    if (!(e instanceof DOMException && e.name === "AbortError")) reportarFallo();   // T-35: sin red o servidor inalcanzable
    throw e;
  }
  medida.servidorMs = res.headers.get("X-Offline-Cache") === "true" ? null : tiempoServidor(res);
  // Respuesta servida por el service worker desde su caché (X-Offline-Cache) = el servidor NO fue alcanzado
  if (res.status === 502 || res.status === 503 || res.status === 504 || res.headers.get("X-Offline-Cache") === "true") reportarFallo(); else reportarExito();

  // 502/503/504 en lecturas (GET): el backend se está reiniciando; se reintenta en silencio
  // 2 veces (1,5 s y 3 s) antes de dar error. Las escrituras no se repiten solas.
  for (let intento = 0; (res.status === 502 || res.status === 503 || res.status === 504) && intento < 2
       && (fetchOptions.method || "GET") === "GET" && res.headers.get("X-Offline-Cache") !== "true"; intento++) {
    medida.descartar = true;
    await sleep(intento === 0 ? 1500 : 3000);
    try {
      res = await fetch(`${BASE}${path}`, {
        credentials: "include",
        headers: { "Content-Type": "application/json", ...fetchOptions.headers },
        ...fetchOptions,
      });
    } catch { break; }
  }

  // 429: respetar Retry-After y reintentar (hasta 2 veces) si la espera es corta
  for (let attempt = 0; res.status === 429 && attempt < 2 && !isAuthEndpoint; attempt++) {
    const retryAfter = parseInt(res.headers.get("Retry-After") || "", 10);
    if (!Number.isFinite(retryAfter) || retryAfter < 0 || retryAfter > MAX_RETRY_AFTER_S) break;
    medida.descartar = true;
    await sleep((retryAfter || 1) * 1000);
    res = await fetch(`${BASE}${path}`, {
      credentials: "include",
      headers: { "Content-Type": "application/json", ...fetchOptions.headers },
      ...fetchOptions,
    });
  }

  if (res.status === 403 && !isAuthEndpoint) {
    res.clone().json().then((b) => redirigirSiDebeCambiarClave(403, b)).catch(() => {});
  }
  if (res.status === 401 && !skipAuth && !isAuthEndpoint) {
    medida.descartar = true;
    const refresco = await refrescarConPaciencia();
    if (refresco === "ok") {
      const retryRes = await fetch(`${BASE}${path}`, {
        credentials: "include",
        headers: { "Content-Type": "application/json", ...fetchOptions.headers },
        ...fetchOptions,
      });
      // Igual que la primera respuesta: 204 o cuerpo vacío no se leen como JSON y un error trae su motivo.
      return leerRespuesta<T>(retryRes, path, fetchOptions.method || "GET");
    }
    if (refresco === "temporal") {
      // El servidor no respondió al refresco: NO es sesión vencida. Se conserva la sesión y se avisa.
      logError("refresh_temporal", { path, method: fetchOptions.method || "GET" });
      throw new Error(ERROR_SERVIDOR_REINICIANDO);
    }
    logError("session_expired", { path, method: fetchOptions.method || "GET" });
    window.location.href = "/webmail/login";
    throw new Error("Session expired");
  }

  return leerRespuesta<T>(res, path, fetchOptions.method || "GET");
}

/** Lee la respuesta: error con el motivo del servidor; 204 o cuerpo vacío (p. ej. DELETE) sin parsear JSON. */
async function leerRespuesta<T>(res: Response, path: string, method: string): Promise<T> {
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    logError("api_error", { path, status: res.status, detail: body.detail, method });
    const detail = Array.isArray(body.detail)
      ? body.detail.map((e: { msg?: string }) => e.msg || JSON.stringify(e)).join('; ')
      : (typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail));
    throw new Error(detail || `HTTP ${res.status}`);
  }
  if (res.status === 204) return undefined as T;
  const text = await res.text();
  if (!text) return undefined as T;
  try { return JSON.parse(text) as T; } catch { return undefined as T; }
}

// ---------------------------------------------------------------------------
// Cache de lectura (2026-08-27): estos endpoints devuelven datos que casi no
// cambian, pero el frontend los pedia decenas de veces por sesion, lo que hacia
// sentir lenta la interfaz. Se cachean por unos segundos y se invalidan solos.
// ---------------------------------------------------------------------------
const CACHE_TTL: Record<string, number> = {
  "/auth/me": 60000,        // el usuario no cambia durante la sesion
  "/branding": 300000,      // el branding practicamente nunca cambia
  "/mail/folders": 15000,   // las carpetas cambian muy poco
  "/mail/stats": 10000,     // los contadores toleran unos segundos
};

const _cache = new Map<string, { t: number; data: unknown }>();

function _ttlDe(path: string): number {
  const limpio = path.split("?")[0];
  return CACHE_TTL[limpio] ?? 0;
}

/** Invalida el cache (todo, o solo las rutas que contengan el texto dado). */
export function invalidarCache(contiene?: string) {
  if (!contiene) { _cache.clear(); return; }
  for (const k of Array.from(_cache.keys())) {
    if (k.includes(contiene)) _cache.delete(k);
  }
}

async function getCacheado<T>(path: string, opts?: { skipAuth?: boolean }): Promise<T> {
  const ttl = _ttlDe(path);
  if (!ttl) return request<T>(path, opts);
  const hit = _cache.get(path);
  if (hit && Date.now() - hit.t < ttl) return hit.data as T;
  const data = await request<T>(path, opts);
  _cache.set(path, { t: Date.now(), data });
  return data as T;
}

// H-01: con cambio de contraseña pendiente el servidor responde 403 a todo salvo cambiarla o
// salir. Se vuelve a la pantalla de entrada, que fuerza el cambio tras iniciar sesión.
function redirigirSiDebeCambiarClave(status: number, body: unknown): void {
  // N-7: lo mismo cuando una cuenta privilegiada aún no activó el segundo factor.
  const d = body as { must_change_password?: boolean; must_setup_2fa?: boolean; detail?: { must_change_password?: boolean; must_setup_2fa?: boolean } } | null;
  if (status === 403 && (d?.must_change_password || d?.detail?.must_change_password || d?.must_setup_2fa || d?.detail?.must_setup_2fa)) {
    if (!window.location.pathname.endsWith('/login')) window.location.assign('/webmail/login');
  }
}

export const api = {
  get: <T>(path: string, opts?: { skipAuth?: boolean }) => getCacheado<T>(path, opts),
  // Las escrituras invalidan el cache de correo para no mostrar datos viejos
  // tras mover / eliminar / marcar mensajes.
  // `signal` (opcional) permite cancelar la petición, p. ej. el botón «Cancelar» de la IA.
  post: <T>(path: string, data?: unknown, opts?: { signal?: AbortSignal }): Promise<T> => {
    invalidarCache("/mail/");
    return request<T>(path, { method: "POST", body: data ? JSON.stringify(data) : undefined, signal: opts?.signal });
  },
  put: <T>(path: string, data?: unknown): Promise<T> => {
    invalidarCache("/mail/");
    return request<T>(path, { method: "PUT", body: data ? JSON.stringify(data) : undefined });
  },
  patch: <T>(path: string, data?: unknown): Promise<T> => {
    invalidarCache("/mail/");
    return request<T>(path, { method: "PATCH", body: data ? JSON.stringify(data) : undefined });
  },
  del: <T>(path: string): Promise<T> => {
    invalidarCache("/mail/");
    return request<T>(path, { method: "DELETE" });
  },
};
