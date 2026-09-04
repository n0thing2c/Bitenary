import { describe, expect, it } from "vitest";

import type { HealthProfileFormValues } from "./types";
import {
  INVALID_PREFERENCE_MESSAGE,
  isValidPreferenceValue,
  validateProfileForm,
} from "./profileForm";

const VALID_VALUES: HealthProfileFormValues = {
  dateOfBirth: "1990-01-01",
  gender: "FEMALE",
  weightKg: "65",
  heightCm: "170",
  activityLevel: "MODERATE",
  primaryGoal: "MAINTAIN",
  targetWeightKg: "",
  allergies: [],
  dietaryRestrictions: [],
  tastes: [],
  dislikes: [],
};

describe("validateProfileForm", () => {
  it("rejects a negative height with a field-level error", () => {
    expect(
      validateProfileForm({ ...VALID_VALUES, heightCm: "-170" }),
    ).toMatchObject({
      heightCm: "Enter a height greater than zero.",
    });
  });

  it("rejects numeric-only food preferences", () => {
    expect(
      validateProfileForm({ ...VALID_VALUES, tastes: ["12345"] }),
    ).toMatchObject({ tastes: INVALID_PREFERENCE_MESSAGE });
  });

  it("allows food preferences that contain letters and numbers", () => {
    expect(isValidPreferenceValue("5-spice")).toBe(true);
    expect(isValidPreferenceValue("12345")).toBe(false);
  });
});
