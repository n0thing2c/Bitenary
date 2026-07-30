import { env } from "../config/env";

async function request(path: string, init?: RequestInit): Promise<Response> {
  const response = await fetch(`${env.backendUrl}${path}`, {
    credentials: "include",
    ...init,
  });

  if (!response.ok) {
    throw new Error(`${init?.method ?? "GET"} ${path} failed with ${response.status}`);
  }

  return response;
}

export async function apiGet<T>(path: string): Promise<T> {
  const response = await request(path);
  return response.json() as Promise<T>;
}

export async function apiPost(path: string, csrfToken?: string): Promise<void> {
  await request(path, {
    method: "POST",
    headers: csrfToken ? { "X-CSRF-Token": csrfToken } : undefined,
  });
}

export async function apiPut<TResponse>(
  path: string,
  body: unknown,
  csrfToken: string,
): Promise<TResponse> {
  const response = await request(path, {
    method: "PUT",
    headers: {
      "Content-Type": "application/json",
      "X-CSRF-Token": csrfToken,
    },
    body: JSON.stringify(body),
  });
  return response.json() as Promise<TResponse>;
}
