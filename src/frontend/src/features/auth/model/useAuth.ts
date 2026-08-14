import { useCallback, useEffect, useState } from "react";

import { AUTH_EXPIRED_EVENT } from "../../../shared/api/authEvents";
import {
  getCurrentUser,
  logout,
  redirectToEndSession,
} from "../api/authApi";
import type { CurrentUser } from "./types";

type AuthState = {
  user: CurrentUser | null;
  isLoading: boolean;
  error: string | null;
};

export function useAuth() {
  const [state, setState] = useState<AuthState>({
    user: null,
    isLoading: true,
    error: null,
  });

  const loadUser = useCallback(async () => {
    setState((current) => ({ ...current, isLoading: true, error: null }));
    try {
      const user = await getCurrentUser();
      setState({ user, isLoading: false, error: null });
    } catch {
      setState({ user: null, isLoading: false, error: null });
    }
  }, []);

  const logoutUser = useCallback(async () => {
    setState((current) => ({ ...current, isLoading: true, error: null }));
    try {
      await logout();
    } catch {
      setState((current) => ({
        ...current,
        isLoading: false,
        error: "Could not log out. Please try again.",
      }));
      return;
    }

    setState({ user: null, isLoading: false, error: null });
    redirectToEndSession();
  }, []);

  useEffect(() => {
    void loadUser();
  }, [loadUser]);

  useEffect(() => {
    const handleAuthExpired = () => {
      setState({ user: null, isLoading: false, error: null });
    };

    window.addEventListener(AUTH_EXPIRED_EVENT, handleAuthExpired);
    return () => {
      window.removeEventListener(AUTH_EXPIRED_EVENT, handleAuthExpired);
    };
  }, []);

  return {
    ...state,
    logoutUser,
  };
}
