import { useCallback, useEffect, useState } from "react";

import { getCurrentUser, logout } from "../api/authApi";
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
      setState({ user: null, isLoading: false, error: null });
    } catch {
      setState({
        user: null,
        isLoading: false,
        error: "Could not log out. Please try again.",
      });
    }
  }, []);

  useEffect(() => {
    void loadUser();
  }, [loadUser]);

  return {
    ...state,
    logoutUser,
  };
}
