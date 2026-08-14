import { env } from "../../../shared/config/env";
import { apiGet, apiPost } from "../../../shared/api/httpClient";
import type { CsrfResponse, CurrentUser } from "../model/types";

const AUTH_RETURN_TO = "/";

export function redirectToLogin(): void {
  window.location.assign(
    `${env.backendUrl}/api/auth/login?return_to=${encodeURIComponent(AUTH_RETURN_TO)}`,
  );
}

export function redirectToSignup(): void {
  window.location.assign(
    `${env.backendUrl}/api/auth/signup?return_to=${encodeURIComponent(AUTH_RETURN_TO)}`,
  );
}

export function redirectToEndSession(): void {
  window.location.assign(`${env.backendUrl}/api/auth/end-session`);
}

export async function getCurrentUser(): Promise<CurrentUser> {
  return apiGet<CurrentUser>("/api/auth/me");
}

export async function logout(): Promise<void> {
  const csrf = await apiGet<CsrfResponse>("/api/auth/csrf");
  await apiPost("/api/auth/logout", csrf.csrf_token);
}
