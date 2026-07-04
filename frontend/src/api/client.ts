const BASE = "/api";

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

  let res = await fetch(`${BASE}${path}`, {
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...fetchOptions.headers,
    },
    ...fetchOptions,
  });

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

export const api = {
  get: <T>(path: string, opts?: { skipAuth?: boolean }) => request<T>(path, opts),
  post: <T>(path: string, data?: unknown) =>
    request<T>(path, { method: "POST", body: data ? JSON.stringify(data) : undefined }),
  put: <T>(path: string, data?: unknown) =>
    request<T>(path, { method: "PUT", body: data ? JSON.stringify(data) : undefined }),
  patch: <T>(path: string, data?: unknown) =>
    request<T>(path, { method: "PATCH", body: data ? JSON.stringify(data) : undefined }),
  del: <T>(path: string) => request<T>(path, { method: "DELETE" }),
};
