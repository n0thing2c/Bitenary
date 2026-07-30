import { apiGet, apiPost, apiPut } from "../../../shared/api/httpClient";
import type { CsrfResponse } from "../../auth/model/types";
import type {
  HealthProfileEnvelope,
  UpsertHealthProfileRequest,
} from "../model/types";

export function getHealthProfile(): Promise<HealthProfileEnvelope> {
  return apiGet<HealthProfileEnvelope>("/api/health-profile");
}

export async function saveHealthProfile(
  profile: UpsertHealthProfileRequest,
): Promise<HealthProfileEnvelope> {
  const csrf = await apiGet<CsrfResponse>("/api/auth/csrf");
  return apiPut<HealthProfileEnvelope>(
    "/api/health-profile",
    profile,
    csrf.csrf_token,
  );
}

export async function skipHealthProfileOnboarding(): Promise<void> {
  const csrf = await apiGet<CsrfResponse>("/api/auth/csrf");
  await apiPost(
    "/api/health-profile/onboarding/skip",
    csrf.csrf_token,
  );
}
