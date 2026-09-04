import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { HealthProfile } from "../model/types";
import { HealthProfileForm } from "./HealthProfileForm";

const PROFILE: HealthProfile = {
  date_of_birth: "1990-01-01",
  gender: "FEMALE",
  weight_kg: 65,
  height_cm: 170,
  activity_level: "MODERATE",
  primary_goal: "MAINTAIN",
  target_weight_kg: null,
  preferences: [],
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

function renderForm(onSubmit = vi.fn()) {
  render(
    <HealthProfileForm
      profile={PROFILE}
      submitLabel="Save profile"
      isSaving={false}
      error={null}
      onSubmit={onSubmit}
    />,
  );
  return onSubmit;
}

describe("HealthProfileForm validation", () => {
  it("shows the application error for a negative height", async () => {
    const onSubmit = renderForm();
    const heightInput = screen.getByRole("spinbutton", { name: /Height/i });

    fireEvent.change(heightInput, { target: { value: "-5" } });
    await userEvent.click(screen.getByRole("button", { name: "Save profile" }));

    expect(
      screen.getByText("Enter a height greater than zero."),
    ).toBeInTheDocument();
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("shows an error and blocks submission for a numeric food preference", async () => {
    const onSubmit = renderForm();
    const tasteInput = screen.getByRole("textbox", {
      name: "Preferred tastes",
    });

    await userEvent.type(tasteInput, "12345");

    expect(
      screen.getByText("Enter a food preference that contains letters."),
    ).toBeInTheDocument();
    expect(tasteInput).toHaveAttribute("aria-invalid", "true");

    await userEvent.click(screen.getByRole("button", { name: "Save profile" }));
    expect(onSubmit).not.toHaveBeenCalled();
  });
});
