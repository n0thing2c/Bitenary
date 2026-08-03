import { env } from "../config/env";

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function request(path: string, init?: RequestInit): Promise<Response> {
  const response = await fetch(`${env.backendUrl}${path}`, {
    credentials: "include",
    ...init,
  });

  if (!response.ok) {
    let message = `${init?.method ?? "GET"} ${path} failed with ${response.status}`;
    try {
      const payload = (await response.json()) as { detail?: string | unknown[] };
      if (typeof payload.detail === "string") {
        message = payload.detail;
      } else if (Array.isArray(payload.detail)) {
        message = payload.detail
          .map((item) => {
            if (typeof item === "object" && item && "msg" in item) {
              return String(item.msg);
            }
            return String(item);
          })
          .join(" ");
      }
    } catch {
      // The response did not include a JSON error body.
    }
    throw new ApiError(response.status, message);
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

export async function apiPostJson<TResponse>(
  path: string,
  body: unknown,
  csrfToken: string,
): Promise<TResponse> {
  const response = await request(path, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-CSRF-Token": csrfToken,
    },
    body: JSON.stringify(body),
  });
  return response.json() as Promise<TResponse>;
}

export async function apiPatch<TResponse>(
  path: string,
  body: unknown,
  csrfToken: string,
): Promise<TResponse> {
  const response = await request(path, {
    method: "PATCH",
    headers: {
      "Content-Type": "application/json",
      "X-CSRF-Token": csrfToken,
    },
    body: JSON.stringify(body),
  });
  return response.json() as Promise<TResponse>;
}

export async function apiDelete(path: string, csrfToken: string): Promise<void> {
  await request(path, {
    method: "DELETE",
    headers: { "X-CSRF-Token": csrfToken },
  });
}
