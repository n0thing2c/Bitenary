import {
  cloneElement,
  useId,
  useState,
  type FormEvent,
  type KeyboardEvent,
  type ReactElement,
  type ReactNode,
} from "react";

import {
  profileToFormValues,
  toLocalDateInputValue,
  toUpsertRequest,
  validateProfileForm,
} from "../model/profileForm";
import type {
  HealthProfile,
  HealthProfileActivityLevel,
  HealthProfileFormValues,
  HealthProfileGender,
  HealthProfilePrimaryGoal,
  UpsertHealthProfileRequest,
} from "../model/types";

import "./HealthProfileForm.css";

type HealthProfileFormProps = {
  profile?: HealthProfile | null;
  submitLabel: string;
  isSaving: boolean;
  error: string | null;
  onSubmit: (profile: UpsertHealthProfileRequest) => Promise<void>;
  onCancel?: () => void;
};

const GENDER_OPTIONS: Array<{ value: HealthProfileGender; label: string }> = [
  { value: "MALE", label: "Male" },
  { value: "FEMALE", label: "Female" },
  { value: "OTHER", label: "Other" },
  { value: "PREFER_NOT_TO_SAY", label: "Prefer not to say" },
];

const ACTIVITY_OPTIONS: Array<{
  value: HealthProfileActivityLevel;
  label: string;
}> = [
  { value: "SEDENTARY", label: "Sedentary (little to no exercise)" },
  { value: "LIGHT", label: "Light activity (1-2 sessions/week)" },
  { value: "MODERATE", label: "Moderate activity (3-4 sessions/week)" },
  { value: "ACTIVE", label: "Active (5-6 sessions/week)" },
  { value: "VERY_ACTIVE", label: "Very active (daily intense exercise)" },
];

const GOAL_OPTIONS: Array<{
  value: HealthProfilePrimaryGoal;
  label: string;
}> = [
  { value: "MAINTAIN", label: "Maintain baseline" },
  { value: "WEIGHT_LOSS", label: "Weight loss" },
  { value: "WEIGHT_GAIN", label: "Weight gain" },
  { value: "MUSCLE_GAIN", label: "Hypertrophy (muscle gain)" },
];

export function HealthProfileForm({
  profile = null,
  submitLabel,
  isSaving,
  error,
  onSubmit,
  onCancel,
}: HealthProfileFormProps) {
  const [values, setValues] = useState<HealthProfileFormValues>(() =>
    profileToFormValues(profile),
  );
  const [errors, setErrors] = useState<Record<string, string>>({});
  const latestDateOfBirth = new Date();
  latestDateOfBirth.setDate(latestDateOfBirth.getDate() - 1);
  const maximumDateOfBirth = toLocalDateInputValue(latestDateOfBirth);

  function updateField<Key extends keyof HealthProfileFormValues>(
    field: Key,
    value: HealthProfileFormValues[Key],
  ) {
    setValues((current) => ({ ...current, [field]: value }));
    setErrors((current) => ({ ...current, [field]: "" }));
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const nextErrors = validateProfileForm(values);
    setErrors(nextErrors);
    if (Object.keys(nextErrors).length > 0) {
      return;
    }
    try {
      await onSubmit(toUpsertRequest(values));
    } catch {
      // The feature hook exposes the request error next to the form actions.
    }
  }

  return (
    <form className="health-profile-form" onSubmit={(event) => void handleSubmit(event)}>
      <fieldset disabled={isSaving}>
        <ProfileFormSection
          index="01"
          eyebrow="Basic biological data"
          title="Your baseline"
          description="Used to personalize future nutrition analysis."
        >
          <div className="health-profile-form__full">
            <span className="health-profile-form__label">Biological sex</span>
            <div
              className="health-profile-form__segments"
              aria-label="Biological sex"
            >
              {GENDER_OPTIONS.map((option) => (
                <label key={option.value}>
                  <input
                    type="radio"
                    name="gender"
                    value={option.value}
                    checked={values.gender === option.value}
                    onChange={() => updateField("gender", option.value)}
                  />
                  <span>{option.label}</span>
                </label>
              ))}
            </div>
            <FieldError message={errors.gender} />
          </div>

          <FormField
            label="Date of birth"
            error={errors.dateOfBirth}
            input={
              <input
                type="date"
                max={maximumDateOfBirth}
                value={values.dateOfBirth}
                onChange={(event) =>
                  updateField("dateOfBirth", event.target.value)
                }
              />
            }
          />
          <FormField
            label="Height"
            unit="cm"
            error={errors.heightCm}
            input={
              <input
                type="number"
                inputMode="decimal"
                min="0.01"
                step="0.01"
                placeholder="e.g. 175"
                value={values.heightCm}
                onChange={(event) => updateField("heightCm", event.target.value)}
              />
            }
          />
          <FormField
            label="Current weight"
            unit="kg"
            error={errors.weightKg}
            input={
              <input
                type="number"
                inputMode="decimal"
                min="0.01"
                step="0.01"
                placeholder="e.g. 72.5"
                value={values.weightKg}
                onChange={(event) => updateField("weightKg", event.target.value)}
              />
            }
          />
        </ProfileFormSection>

        <ProfileFormSection
          index="02"
          eyebrow="Activity & goals"
          title="Performance direction"
          description="Tell Bitenary how active you are and what you want to achieve."
        >
          <FormField
            label="Activity level"
            input={
              <select
                value={values.activityLevel}
                onChange={(event) =>
                  updateField(
                    "activityLevel",
                    event.target.value as HealthProfileActivityLevel,
                  )
                }
              >
                {ACTIVITY_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            }
          />
          <FormField
            label="Primary objective"
            input={
              <select
                value={values.primaryGoal}
                onChange={(event) =>
                  updateField(
                    "primaryGoal",
                    event.target.value as HealthProfilePrimaryGoal,
                  )
                }
              >
                {GOAL_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            }
          />
          <FormField
            label="Target weight"
            unit="kg"
            error={errors.targetWeightKg}
            hint="Optional"
            input={
              <input
                type="number"
                inputMode="decimal"
                min="0.01"
                step="0.01"
                placeholder="e.g. 70.0"
                value={values.targetWeightKg}
                onChange={(event) =>
                  updateField("targetWeightKg", event.target.value)
                }
              />
            }
          />
        </ProfileFormSection>

        <ProfileFormSection
          index="03"
          eyebrow="Dietary parameters"
          title="Food preferences"
          description="Add each item separately. Press Enter or use the add button."
        >
          <TagInput
            label="Allergies"
            placeholder="e.g. peanuts"
            values={values.allergies}
            tone="danger"
            onChange={(nextValues) => updateField("allergies", nextValues)}
          />
          <TagInput
            label="Dietary restrictions"
            placeholder="e.g. lactose-free"
            values={values.dietaryRestrictions}
            tone="neutral"
            onChange={(nextValues) =>
              updateField("dietaryRestrictions", nextValues)
            }
          />
          <TagInput
            label="Preferred tastes"
            placeholder="e.g. spicy"
            values={values.tastes}
            tone="positive"
            onChange={(nextValues) => updateField("tastes", nextValues)}
          />
          <TagInput
            label="Disliked foods"
            placeholder="e.g. mushrooms"
            values={values.dislikes}
            tone="warning"
            onChange={(nextValues) => updateField("dislikes", nextValues)}
          />
        </ProfileFormSection>
      </fieldset>

      {error ? (
        <p className="health-profile-form__submit-error" role="alert">
          {error}
        </p>
      ) : null}

      <div className="health-profile-form__actions">
        {onCancel ? (
          <button
            className="health-profile-form__button health-profile-form__button--secondary"
            type="button"
            disabled={isSaving}
            onClick={onCancel}
          >
            Cancel
          </button>
        ) : null}
        <button
          className="health-profile-form__button health-profile-form__button--primary"
          type="submit"
          disabled={isSaving}
        >
          {isSaving ? "Saving..." : submitLabel}
          {!isSaving ? <span aria-hidden="true">→</span> : null}
        </button>
      </div>
    </form>
  );
}

function ProfileFormSection({
  index,
  eyebrow,
  title,
  description,
  children,
}: {
  index: string;
  eyebrow: string;
  title: string;
  description: string;
  children: ReactNode;
}) {
  return (
    <section className="health-profile-form__section">
      <div className="health-profile-form__section-heading">
        <span className="health-profile-form__section-index">{index}</span>
        <div>
          <p>{eyebrow}</p>
          <h2>{title}</h2>
          <span>{description}</span>
        </div>
      </div>
      <div className="health-profile-form__grid">{children}</div>
    </section>
  );
}

function FormField({
  label,
  unit,
  hint,
  error,
  input,
}: {
  label: string;
  unit?: string;
  hint?: string;
  error?: string;
  input: ReactElement<Record<string, unknown>>;
}) {
  const id = useId();
  return (
    <label className="health-profile-form__field" htmlFor={id}>
      <span className="health-profile-form__field-heading">
        <span className="health-profile-form__label">{label}</span>
        {hint ? <span>{hint}</span> : null}
      </span>
      <span className="health-profile-form__input-wrap">
        {cloneWithId(input, id)}
        {unit ? <span className="health-profile-form__unit">{unit}</span> : null}
      </span>
      <FieldError message={error} />
    </label>
  );
}

function cloneWithId(
  element: ReactElement<Record<string, unknown>>,
  id: string,
) {
  return cloneElement(element, { id });
}

function FieldError({ message }: { message?: string }) {
  return message ? (
    <span className="health-profile-form__field-error">{message}</span>
  ) : null;
}

function TagInput({
  label,
  placeholder,
  values,
  tone,
  onChange,
}: {
  label: string;
  placeholder: string;
  values: string[];
  tone: "danger" | "neutral" | "positive" | "warning";
  onChange: (values: string[]) => void;
}) {
  const id = useId();
  const [draft, setDraft] = useState("");

  function addDraft() {
    const value = draft.trim().replace(/\s+/g, " ");
    if (
      !value ||
      value.length > 100 ||
      values.some((item) => item.toLowerCase() === value.toLowerCase())
    ) {
      setDraft("");
      return;
    }
    onChange([...values, value]);
    setDraft("");
  }

  function handleKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === "Enter" || event.key === ",") {
      event.preventDefault();
      addDraft();
    }
  }

  return (
    <div className="health-profile-form__tag-field">
      <label className="health-profile-form__label" htmlFor={id}>
        {label}
      </label>
      <div className="health-profile-form__tag-box">
        <div className="health-profile-form__tags">
          {values.map((value) => (
            <span
              className={`health-profile-form__tag health-profile-form__tag--${tone}`}
              key={value.toLowerCase()}
            >
              {value}
              <button
                type="button"
                aria-label={`Remove ${value}`}
                onClick={() =>
                  onChange(values.filter((candidate) => candidate !== value))
                }
              >
                ×
              </button>
            </span>
          ))}
        </div>
        <div className="health-profile-form__tag-entry">
          <input
            id={id}
            type="text"
            maxLength={100}
            placeholder={placeholder}
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            onKeyDown={handleKeyDown}
            onBlur={addDraft}
          />
          <button
            type="button"
            disabled={!draft.trim()}
            onMouseDown={(event) => event.preventDefault()}
            onClick={addDraft}
          >
            Add
          </button>
        </div>
      </div>
    </div>
  );
}
