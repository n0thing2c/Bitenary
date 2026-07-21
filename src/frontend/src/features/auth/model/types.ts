export type UserStatus = "ACTIVE" | "DISABLED";

export type CurrentUser = {
  user_id: string;
  authentik_sub: string;
  username: string;
  email: string | null;
  status: UserStatus;
};

export type CsrfResponse = {
  csrf_token: string;
};
