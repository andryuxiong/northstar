const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

export function getToken(): string | null {
  return localStorage.getItem("token");
}

export function setToken(token: string) {
  localStorage.setItem("token", token);
}

export async function apiFetch<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const request = async (mayRefreshLocalSession: boolean): Promise<T> => {
    const token = getToken();
    const headers = new Headers(options.headers || {});
    if (token) headers.set("Authorization", `Bearer ${token}`);
    if (!headers.has("Content-Type") && options.body)
      headers.set("Content-Type", "application/json");

    const res = await fetch(`${API_URL}${path}`, { ...options, headers });
    if (
      res.status === 401 &&
      mayRefreshLocalSession &&
      !path.startsWith("/auth/")
    ) {
      await localLogin();
      return request(false);
    }
    if (!res.ok) {
      let message = `API error ${res.status}`;
      try {
        const payload = await res.json();
        const detail = payload?.detail;
        if (typeof detail === "string") message = detail;
        else if (typeof detail?.message === "string") message = detail.message;
        else if (typeof payload?.error?.message === "string")
          message = payload.error.message;
      } catch {
        // Preserve the status-based fallback when the response is not JSON.
      }
      throw new Error(message);
    }
    if (res.status === 204) return undefined as T;
    const text = await res.text();
    if (!text) return undefined as T;
    return JSON.parse(text) as T;
  };
  return request(true);
}

let localLoginInFlight: Promise<{ access_token: string }> | null = null;

export async function localLogin() {
  if (localLoginInFlight) return localLoginInFlight;
  localLoginInFlight = (async () => {
    const res = await fetch(`${API_URL}/auth/local`, { method: "POST" });
    if (!res.ok) throw new Error("Local login failed");
    const data = (await res.json()) as { access_token: string };
    setToken(data.access_token);
    return data;
  })();
  try {
    return await localLoginInFlight;
  } finally {
    localLoginInFlight = null;
  }
}
