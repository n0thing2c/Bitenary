import { env } from "../config/env";
import { notifyAuthExpired } from "./authEvents";

const AUTH_REFRESH_EXCLUDED_PATHS = new Set([
  "/api/auth/csrf",
  "/api/auth/refresh",
  "/api/auth/login",
  "/api/auth/signup",
  "/api/auth/logout",
]);

let refreshPromise: Promise<void> | null = null;
let sessionRevision = 0;

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

function fetchApi(path: string, init?: RequestInit): Promise<Response> {
  return fetch(`${env.backendUrl}${path}`, {
    credentials: "include",
    ...init,
  });
}

async function refreshAccessToken(): Promise<void> {
  const csrfResponse = await fetchApi("/api/auth/csrf");
  if (!csrfResponse.ok) {
    throw new ApiError(csrfResponse.status, "Could not obtain a CSRF token");
  }

  const csrfPayload = (await csrfResponse.json()) as { csrf_token?: unknown };
  if (typeof csrfPayload.csrf_token !== "string" || !csrfPayload.csrf_token) {
    throw new ApiError(500, "The CSRF response was invalid");
  }

  const refreshResponse = await fetchApi("/api/auth/refresh", {
    method: "POST",
    headers: { "X-CSRF-Token": csrfPayload.csrf_token },
  });
  if (!refreshResponse.ok) {
    throw new ApiError(refreshResponse.status, "Could not refresh the session");
  }
  sessionRevision += 1;
}

function ensureAccessToken(): Promise<void> {
  if (!refreshPromise) {
    refreshPromise = refreshAccessToken()
      .catch((error: unknown) => {
        notifyAuthExpired();
        throw error;
      })
      .finally(() => {
        refreshPromise = null;
      });
  }
  return refreshPromise;
}

function shouldRefresh(path: string): boolean {
  return !AUTH_REFRESH_EXCLUDED_PATHS.has(path);
}

async function apiErrorFromResponse(
  response: Response,
  path: string,
  init?: RequestInit,
): Promise<ApiError> {
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
  return new ApiError(response.status, message);
}

async function request(path: string, init?: RequestInit): Promise<Response> {
  const revisionAtRequestStart = sessionRevision;
  const response = await fetchApi(path, init);

  if (response.status === 401 && shouldRefresh(path)) {
    if (revisionAtRequestStart === sessionRevision) {
      try {
        await ensureAccessToken();
      } catch {
        throw await apiErrorFromResponse(response, path, init);
      }
    }

    const retriedResponse = await fetchApi(path, init);
    if (retriedResponse.status === 401) {
      notifyAuthExpired();
    }
    if (!retriedResponse.ok) {
      throw await apiErrorFromResponse(retriedResponse, path, init);
    }
    return retriedResponse;
  }

  if (!response.ok) {
    throw await apiErrorFromResponse(response, path, init);
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
