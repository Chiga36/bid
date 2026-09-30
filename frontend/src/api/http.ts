import { ApiError } from "./types";

// Dynamic for the same reason main.py's CORS origin regex is dynamic (any localhost/127.0.0.1
// port, not a hardcoded 5173): a hardcoded "127.0.0.1:5000" fallback only ever works when the
// frontend and backend are on the exact same machine. Opening the frontend from another device
// on the network (its LAN IP) would otherwise still try to hit that *device's own* localhost,
// which is wrong. Deriving from window.location.hostname instead means the frontend always
// targets the backend on whatever host it was itself loaded from. VITE_API_BASE_URL (set at
// build time) still wins outright when explicitly configured, e.g. a real deployment where the
// backend lives on a different host than the frontend.
const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? `http://${window.location.hostname}:${import.meta.env.VITE_API_PORT ?? "5000"}`;

async function handle<T>(response: Response): Promise<T> {
  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = await response.json();
      detail = body.detail ?? detail;
    } catch {
      // response wasn't JSON — fall back to statusText, already set above
    }
    throw new ApiError(response.status, detail);
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return response.json() as Promise<T>;
}

export async function apiGet<T>(path: string): Promise<T> {
  const response = await fetch(`${BASE_URL}${path}`);
  return handle<T>(response);
}

export async function apiPost<T>(path: string, body?: unknown): Promise<T> {
  const response = await fetch(`${BASE_URL}${path}`, {
    method: "POST",
    headers: body !== undefined ? { "Content-Type": "application/json" } : undefined,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  return handle<T>(response);
}

export async function apiUpload<T>(path: string, formData: FormData): Promise<T> {
  const response = await fetch(`${BASE_URL}${path}`, {
    method: "POST",
    body: formData,
  });
  return handle<T>(response);
}

export async function apiPut<T>(path: string, body?: unknown): Promise<T> {
  const response = await fetch(`${BASE_URL}${path}`, {
    method: "PUT",
    headers: body !== undefined ? { "Content-Type": "application/json" } : undefined,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  return handle<T>(response);
}

export async function apiDelete<T>(path: string): Promise<T> {
  const response = await fetch(`${BASE_URL}${path}`, { method: "DELETE" });
  return handle<T>(response);
}
