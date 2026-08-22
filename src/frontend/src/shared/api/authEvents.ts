export const AUTH_EXPIRED_EVENT = "bitenary:auth-expired";

export function notifyAuthExpired(): void {
  window.dispatchEvent(new Event(AUTH_EXPIRED_EVENT));
}
