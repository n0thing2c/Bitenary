import type { UserStatus } from "../../auth/model/types";

export type HealthProfileGender =
  | "MALE"
  | "FEMALE"
  | "OTHER"
  | "PREFER_NOT_TO_SAY";

export type HealthProfileActivityLevel =
  | "SEDENTARY"
  | "LIGHT"
  | "MODERATE"
  | "ACTIVE"
  | "VERY_ACTIVE";

export type HealthProfilePrimaryGoal =
  | "MAINTAIN"
  | "WEIGHT_LOSS"
  | "WEIGHT_GAIN"
  | "MUSCLE_GAIN";

export type HealthPreferenceType =
  | "ALLERGY"
  | "DIETARY_RESTRICTION"
  | "TASTE"
  | "DISLIKE";

export type HealthProfileOnboardingState =
  | "NOT_STARTED"
  | "SKIPPED"
  | "COMPLETED";

export type HealthPreference = {
  preference_type: HealthPreferenceType;
  value: string;
};

export type HealthProfile = {
  date_of_birth: string;
  gender: HealthProfileGender;
  weight_kg: number;
  height_cm: number;
  activity_level: HealthProfileActivityLevel;
  primary_goal: HealthProfilePrimaryGoal;
  target_weight_kg: number | null;
  preferences: HealthPreference[];
  created_at: string;
  updated_at: string;
};

export type AccountSummary = {
  user_id: string;
  username: string;
  email: string | null;
  status: UserStatus;
};

export type HealthProfileEnvelope = {
  onboarding_state: HealthProfileOnboardingState;
  account: AccountSummary;
  health_profile: HealthProfile | null;
};

export type UpsertHealthProfileRequest = {
  date_of_birth: string;
  gender: HealthProfileGender;
  weight_kg: number;
  height_cm: number;
  activity_level: HealthProfileActivityLevel;
  primary_goal: HealthProfilePrimaryGoal;
  target_weight_kg: number | null;
  preferences: HealthPreference[];
};

export type HealthProfileFormValues = {
  dateOfBirth: string;
  gender: HealthProfileGender | "";
  weightKg: string;
  heightCm: string;
  activityLevel: HealthProfileActivityLevel;
  primaryGoal: HealthProfilePrimaryGoal;
  targetWeightKg: string;
  allergies: string[];
  dietaryRestrictions: string[];
  tastes: string[];
  dislikes: string[];
};
