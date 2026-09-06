const BASE = "/api";
import { reportarFallo, reportarExito } from "../lib/conexion";   // T-35: estado real de conexión

// Error logger for traceability
function logError(context: string, details: Record<string, unknown>) {
  const entry = {
    ts: new Date().toISOString(),
    context,
    ...details,
  };
  console.error("[Maquita]", context, details);
  // Store last 50 errors in sessionStorage for debugging
  try {
    const logs = JSON.parse(sessionStorage.getItem("maquita_errors") || "[]");
    logs.push(entry);
    if (logs.length > 50) logs.shift();
    sessionStorage.setItem("maquita_errors", JSON.stringify(logs));
  } catch { /* ignore */ }
}

let isRefreshing = false;
let refreshPromise: Promise<boolean> | null = null;

async function tryRefresh(): Promise<boolean> {
  if (isRefreshing && refreshPromise) return refreshPromise;
  isRefreshing = true;
  refreshPromise = fetch(`${BASE}/auth/refresh`, {
    method: "POST",
    credentials: "include",
  })
    .then((res) => {
      if (!res.ok) return false;
      return res.json().then((data: { refreshed?: boolean }) => data.refreshed !== false);
    })
    .catch(() => false)
    .finally(() => {
      isRefreshing = false;
      refreshPromise = null;
    });
  return refreshPromise;
}

// Máxima espera (s) que aceptamos para reintentar automáticamente tras un 429
const MAX_RETRY_AFTER_S = 15;
const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

async function request<T>(path: string, options: RequestInit & { skipAuth?: boolean } = {}): Promise<T> {
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
    reportarFallo();   // T-35: sin red o servidor inalcanzable
    throw e;
  }
  // Respuesta servida por el service worker desde su caché (X-Offline-Cache) = el servidor NO fue alcanzado
  if (res.status === 502 || res.status === 503 || res.status === 504 || res.headers.get("X-Offline-Cache") === "true") reportarFallo(); else reportarExito();

  // 429: respetar Retry-After y reintentar (hasta 2 veces) si la espera es corta
  for (let attempt = 0; res.status === 429 && attempt < 2 && !isAuthEndpoint; attempt++) {
    const retryAfter = parseInt(res.headers.get("Retry-After") || "", 10);
    if (!Number.isFinite(retryAfter) || retryAfter < 0 || retryAfter > MAX_RETRY_AFTER_S) break;
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
    const refreshed = await tryRefresh();
    if (refreshed) {
      const retryRes = await fetch(`${BASE}${path}`, {
        credentials: "include",
        headers: { "Content-Type": "application/json", ...fetchOptions.headers },
        ...fetchOptions,
      });
      if (!retryRes.ok) throw new Error(`HTTP ${retryRes.status}`);
      return retryRes.json();
    }
    logError("session_expired", { path, method: fetchOptions.method || "GET" });
    window.location.href = "/webmail/login";
    throw new Error("Session expired");
  }

  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    logError("api_error", { path, status: res.status, detail: body.detail, method: fetchOptions.method || "GET" });
    const detail = Array.isArray(body.detail)
      ? body.detail.map((e: any) => e.msg || JSON.stringify(e)).join('; ')
      : (typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail));
    throw new Error(detail || `HTTP ${res.status}`);
  }

  // 204 No Content o cuerpo vacío (p. ej. DELETE) → no intentar parsear JSON
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
  const d = body as { must_change_password?: boolean; detail?: { must_change_password?: boolean } } | null;
  if (status === 403 && (d?.must_change_password || d?.detail?.must_change_password)) {
    if (!window.location.pathname.endsWith('/login')) window.location.assign('/webmail/login');
  }
}

export const api = {
  get: <T>(path: string, opts?: { skipAuth?: boolean }) => getCacheado<T>(path, opts),
  // Las escrituras invalidan el cache de correo para no mostrar datos viejos
  // tras mover / eliminar / marcar mensajes.
  post: <T>(path: string, data?: unknown): Promise<T> => {
    invalidarCache("/mail/");
    return request<T>(path, { method: "POST", body: data ? JSON.stringify(data) : undefined });
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
