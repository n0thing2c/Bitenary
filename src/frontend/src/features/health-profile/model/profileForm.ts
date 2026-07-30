import type {
  HealthPreference,
  HealthPreferenceType,
  HealthProfile,
  HealthProfileFormValues,
  UpsertHealthProfileRequest,
} from "./types";

export const EMPTY_PROFILE_FORM: HealthProfileFormValues = {
  dateOfBirth: "",
  gender: "",
  weightKg: "",
  heightCm: "",
  activityLevel: "MODERATE",
  primaryGoal: "MAINTAIN",
  targetWeightKg: "",
  allergies: [],
  dietaryRestrictions: [],
  tastes: [],
  dislikes: [],
};

const PREFERENCE_FIELD_BY_TYPE: Record<
  HealthPreferenceType,
  keyof Pick<
    HealthProfileFormValues,
    "allergies" | "dietaryRestrictions" | "tastes" | "dislikes"
  >
> = {
  ALLERGY: "allergies",
  DIETARY_RESTRICTION: "dietaryRestrictions",
  TASTE: "tastes",
  DISLIKE: "dislikes",
};

export function profileToFormValues(
  profile: HealthProfile | null,
): HealthProfileFormValues {
  if (!profile) {
    return { ...EMPTY_PROFILE_FORM };
  }

  const values: HealthProfileFormValues = {
    dateOfBirth: profile.date_of_birth,
    gender: profile.gender,
    weightKg: String(profile.weight_kg),
    heightCm: String(profile.height_cm),
    activityLevel: profile.activity_level,
    primaryGoal: profile.primary_goal,
    targetWeightKg:
      profile.target_weight_kg === null ? "" : String(profile.target_weight_kg),
    allergies: [],
    dietaryRestrictions: [],
    tastes: [],
    dislikes: [],
  };

  for (const preference of profile.preferences) {
    values[PREFERENCE_FIELD_BY_TYPE[preference.preference_type]].push(
      preference.value,
    );
  }
  return values;
}

export function validateProfileForm(
  values: HealthProfileFormValues,
): Record<string, string> {
  const errors: Record<string, string> = {};
  const today = toLocalDateInputValue(new Date());

  if (!values.gender) {
    errors.gender = "Choose a biological sex option.";
  }
  if (!values.dateOfBirth) {
    errors.dateOfBirth = "Enter your date of birth.";
  } else if (values.dateOfBirth >= today) {
    errors.dateOfBirth = "Date of birth must be in the past.";
  }
  if (!isPositiveNumber(values.heightCm)) {
    errors.heightCm = "Enter a height greater than zero.";
  }
  if (!isPositiveNumber(values.weightKg)) {
    errors.weightKg = "Enter a weight greater than zero.";
  }
  if (
    values.targetWeightKg &&
    !isPositiveNumber(values.targetWeightKg)
  ) {
    errors.targetWeightKg = "Target weight must be greater than zero.";
  }

  return errors;
}

export function toLocalDateInputValue(value: Date): string {
  const localValue = new Date(
    value.getTime() - value.getTimezoneOffset() * 60_000,
  );
  return localValue.toISOString().slice(0, 10);
}

export function toUpsertRequest(
  values: HealthProfileFormValues,
): UpsertHealthProfileRequest {
  if (!values.gender) {
    throw new Error("Profile gender is required");
  }

  return {
    date_of_birth: values.dateOfBirth,
    gender: values.gender,
    weight_kg: Number(values.weightKg),
    height_cm: Number(values.heightCm),
    activity_level: values.activityLevel,
    primary_goal: values.primaryGoal,
    target_weight_kg: values.targetWeightKg
      ? Number(values.targetWeightKg)
      : null,
    preferences: [
      ...toPreferences("ALLERGY", values.allergies),
      ...toPreferences("DIETARY_RESTRICTION", values.dietaryRestrictions),
      ...toPreferences("TASTE", values.tastes),
      ...toPreferences("DISLIKE", values.dislikes),
    ],
  };
}

function isPositiveNumber(value: string): boolean {
  const number = Number(value);
  return value.trim() !== "" && Number.isFinite(number) && number > 0;
}

function toPreferences(
  preferenceType: HealthPreferenceType,
  values: string[],
): HealthPreference[] {
  return values.map((value) => ({
    preference_type: preferenceType,
    value,
  }));
}
