import { env } from "../config/env";

export async function apiGet<T>(path: string): Promise<T> {
  const response = await fetch(`${env.backendUrl}${path}`, {
    credentials: "include",
  });

  if (!response.ok) {
    throw new Error(`GET ${path} failed with ${response.status}`);
  }

  return response.json() as Promise<T>;
}

export async function apiPost(path: string, csrfToken?: string): Promise<void> {
  const response = await fetch(`${env.backendUrl}${path}`, {
    method: "POST",
    credentials: "include",
    headers: csrfToken ? { "X-CSRF-Token": csrfToken } : undefined,
  });

  if (!response.ok) {
    throw new Error(`POST ${path} failed with ${response.status}`);
  }
}
