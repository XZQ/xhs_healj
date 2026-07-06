// API client layer — single source of truth for request helpers.
// Keeps auth/token logic out of the UI components.

const API = "/api/v1";
const TOKEN_KEY = "xhs_health_api_token";

function getStoredToken() {
  return window.localStorage.getItem(TOKEN_KEY) || "";
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers);
  const token = getStoredToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  const response = await fetch(`${API}${path}`, { ...init, headers });
  if (response.status === 401) throw new Error("API token 无效或缺失，请在右上角设置");
  if (!response.ok) throw new Error(await response.text());
  return response.json() as Promise<T>;
}

async function requestWithMeta<T>(
  path: string,
  init?: RequestInit
): Promise<{ data: T; total: number | null }> {
  const headers = new Headers(init?.headers);
  const token = getStoredToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  const response = await fetch(`${API}${path}`, { ...init, headers });
  if (response.status === 401) throw new Error("API token 无效或缺失，请在右上角设置");
  if (!response.ok) throw new Error(await response.text());
  const raw = response.headers.get("X-Total-Count");
  const total = raw !== null ? Number(raw) : null;
  return { data: (await response.json()) as T, total: Number.isFinite(total) ? total : null };
}

async function downloadApiFile(path: string, filename: string) {
  const headers = new Headers();
  const token = getStoredToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  const response = await fetch(`${API}${path}`, { headers });
  if (response.status === 401) throw new Error("API token 无效或缺失，请在右上角设置");
  if (!response.ok) throw new Error(await response.text());
  const blob = await response.blob();
  const url = window.URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(url);
}

export { request, requestWithMeta, downloadApiFile, getStoredToken, TOKEN_KEY };
