const BASE = "/api";

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const token = localStorage.getItem("admin_token");
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(`${BASE}${path}`, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  });

  if (res.status === 401) {
    localStorage.removeItem("admin_token");
    localStorage.removeItem("admin_user");
    if (path !== "/auth/login") {
      window.location.href = "/login";
      throw new Error("No autorizado");
    }
    const err = await res.json().catch(() => ({ detail: "Credenciales inválidas" }));
    throw new Error(err.detail || "Credenciales inválidas");
  }

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || res.statusText);
  }

  return res.json();
}

export const api = {
  get: <T>(path: string) => request<T>("GET", path),
  post: <T>(path: string, body?: unknown) => request<T>("POST", path, body),
  put: <T>(path: string, body?: unknown) => request<T>("PUT", path, body),
  del: <T>(path: string) => request<T>("DELETE", path),
};
