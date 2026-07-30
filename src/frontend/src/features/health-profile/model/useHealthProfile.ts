import { useCallback, useEffect, useState } from "react";

import {
  getHealthProfile,
  saveHealthProfile,
  skipHealthProfileOnboarding,
} from "../api/healthProfileApi";
import type {
  HealthProfileEnvelope,
  UpsertHealthProfileRequest,
} from "./types";

type HealthProfileState = {
  data: HealthProfileEnvelope | null;
  isLoading: boolean;
  isSaving: boolean;
  error: string | null;
};

export function useHealthProfile() {
  const [state, setState] = useState<HealthProfileState>({
    data: null,
    isLoading: true,
    isSaving: false,
    error: null,
  });

  const loadProfile = useCallback(async () => {
    setState((current) => ({ ...current, isLoading: true, error: null }));
    try {
      const data = await getHealthProfile();
      setState({ data, isLoading: false, isSaving: false, error: null });
    } catch {
      setState((current) => ({
        ...current,
        isLoading: false,
        error: "We could not load your health profile. Please try again.",
      }));
    }
  }, []);

  const saveProfile = useCallback(
    async (profile: UpsertHealthProfileRequest) => {
      setState((current) => ({ ...current, isSaving: true, error: null }));
      try {
        const data = await saveHealthProfile(profile);
        setState({ data, isLoading: false, isSaving: false, error: null });
      } catch (error) {
        setState((current) => ({
          ...current,
          isSaving: false,
          error: "Your changes could not be saved. Please try again.",
        }));
        throw error;
      }
    },
    [],
  );

  const skipOnboarding = useCallback(async () => {
    setState((current) => ({ ...current, isSaving: true, error: null }));
    try {
      await skipHealthProfileOnboarding();
      const data = await getHealthProfile();
      setState({ data, isLoading: false, isSaving: false, error: null });
    } catch (error) {
      setState((current) => ({
        ...current,
        isSaving: false,
        error: "We could not skip profile setup. Please try again.",
      }));
      throw error;
    }
  }, []);

  useEffect(() => {
    void loadProfile();
  }, [loadProfile]);

  return {
    ...state,
    loadProfile,
    saveProfile,
    skipOnboarding,
  };
}
