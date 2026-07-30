import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import type {
  AccountSummary,
  HealthPreferenceType,
  HealthProfile,
  HealthProfileActivityLevel,
  HealthProfileGender,
  HealthProfilePrimaryGoal,
  UpsertHealthProfileRequest,
} from "../../features/health-profile/model/types";
import { HealthProfileForm } from "../../features/health-profile/ui/HealthProfileForm";

import "./HealthProfilePage.css";

type HealthProfilePageProps = {
  account: AccountSummary;
  profile: HealthProfile | null;
  isSaving: boolean;
  error: string | null;
  onSave: (profile: UpsertHealthProfileRequest) => Promise<void>;
};

const GENDER_LABELS: Record<HealthProfileGender, string> = {
  MALE: "Male",
  FEMALE: "Female",
  OTHER: "Other",
  PREFER_NOT_TO_SAY: "Prefer not to say",
};

const ACTIVITY_LABELS: Record<HealthProfileActivityLevel, string> = {
  SEDENTARY: "Sedentary",
  LIGHT: "Light activity",
  MODERATE: "Moderate activity",
  ACTIVE: "Active",
  VERY_ACTIVE: "Very active",
};

const GOAL_LABELS: Record<HealthProfilePrimaryGoal, string> = {
  MAINTAIN: "Maintain baseline",
  WEIGHT_LOSS: "Weight loss",
  WEIGHT_GAIN: "Weight gain",
  MUSCLE_GAIN: "Muscle gain",
};

export function HealthProfilePage({
  account,
  profile,
  isSaving,
  error,
  onSave,
}: HealthProfilePageProps) {
  const navigate = useNavigate();
  const [isEditing, setIsEditing] = useState(false);

  useEffect(() => {
    if (!isEditing) {
      return;
    }
    function closeOnEscape(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setIsEditing(false);
      }
    }
    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, [isEditing]);

  if (!profile) {
    return (
      <main className="health-profile-page">
        <PageHeader />
        <section className="health-profile-empty">
          <span className="health-profile-empty__number">00</span>
          <p>Profile not initialized</p>
          <h1>Build your biological baseline</h1>
          <span>
            Add your biological data, activity level, goals and food preferences
            when you are ready.
          </span>
          <button type="button" onClick={() => navigate("/profile/setup")}>
            Initialize profile <span aria-hidden="true">→</span>
          </button>
        </section>
      </main>
    );
  }

  async function saveAndClose(values: UpsertHealthProfileRequest) {
    await onSave(values);
    setIsEditing(false);
  }

  return (
    <main className="health-profile-page">
      <PageHeader onEdit={() => setIsEditing(true)} />

      <div className="health-profile-layout">
        <div className="health-profile-content">
          <section
            className="health-profile-panel health-profile-overview"
            aria-labelledby="biological-status-title"
          >
            <div className="health-profile-panel__heading">
              <div>
                <p>Biological status</p>
                <h1 id="biological-status-title">Your current baseline</h1>
                <span>
                  Physiological data currently stored for personalization.
                </span>
              </div>
              <span className="health-profile-panel__badge">Active profile</span>
            </div>

            <div className="health-profile-stat-grid">
              <ProfileStat
                eyebrow="Age"
                value={String(calculateAge(profile.date_of_birth))}
                detail={formatDate(profile.date_of_birth)}
              />
              <ProfileStat
                eyebrow="Current weight"
                value={formatNumber(profile.weight_kg)}
                unit="kg"
                detail={
                  profile.target_weight_kg
                    ? `Target ${formatNumber(profile.target_weight_kg)} kg`
                    : "No target set"
                }
              />
              <ProfileStat
                eyebrow="Height"
                value={formatNumber(profile.height_cm)}
                unit="cm"
                detail={GENDER_LABELS[profile.gender]}
              />
            </div>
          </section>

          <section className="health-profile-panel">
            <div className="health-profile-panel__heading">
              <div>
                <p>Activity & goals</p>
                <h2>Performance direction</h2>
              </div>
            </div>
            <div className="health-profile-detail-grid">
              <ProfileDetail
                label="Training intensity"
                value={ACTIVITY_LABELS[profile.activity_level]}
                description={activityDescription(profile.activity_level)}
              />
              <ProfileDetail
                label="Primary objective"
                value={GOAL_LABELS[profile.primary_goal]}
                description="Used to guide future recipe and meal-plan recommendations."
              />
              <ProfileDetail
                label="Target weight"
                value={
                  profile.target_weight_kg
                    ? `${formatNumber(profile.target_weight_kg)} kg`
                    : "Not specified"
                }
                description="You can update this target at any time."
              />
            </div>
          </section>

          <section className="health-profile-panel">
            <div className="health-profile-panel__heading">
              <div>
                <p>Dietary parameters</p>
                <h2>Food preferences</h2>
                <span>
                  These details will help future recommendations respect your
                  needs.
                </span>
              </div>
            </div>
            <div className="health-profile-preference-grid">
              <PreferenceGroup
                label="Allergies"
                type="ALLERGY"
                profile={profile}
                tone="danger"
              />
              <PreferenceGroup
                label="Dietary restrictions"
                type="DIETARY_RESTRICTION"
                profile={profile}
                tone="neutral"
              />
              <PreferenceGroup
                label="Preferred tastes"
                type="TASTE"
                profile={profile}
                tone="positive"
              />
              <PreferenceGroup
                label="Disliked foods"
                type="DISLIKE"
                profile={profile}
                tone="warning"
              />
            </div>
          </section>
        </div>

        <aside className="health-profile-rail">
          <section className="health-profile-rail__card">
            <p>Account</p>
            <div className="health-profile-account">
              <span>{account.username.slice(0, 1).toUpperCase()}</span>
              <div>
                <strong>{account.username}</strong>
                <small>{account.email ?? "No email available"}</small>
              </div>
            </div>
            <dl>
              <div>
                <dt>Status</dt>
                <dd>{account.status.toLowerCase()}</dd>
              </div>
              <div>
                <dt>Profile updated</dt>
                <dd>{formatDate(profile.updated_at)}</dd>
              </div>
            </dl>
          </section>

          <section className="health-profile-rail__notice">
            <span aria-hidden="true">i</span>
            <div>
              <strong>Calculated metrics are coming later</strong>
              <p>
                Energy, macro and hydration targets will appear after the
                calculation model has been reviewed.
              </p>
            </div>
          </section>
        </aside>
      </div>

      {isEditing ? (
        <div
          className="profile-drawer-backdrop"
          role="presentation"
          onMouseDown={(event) => {
            if (event.target === event.currentTarget && !isSaving) {
              setIsEditing(false);
            }
          }}
        >
          <aside
            className="profile-drawer"
            role="dialog"
            aria-modal="true"
            aria-labelledby="profile-drawer-title"
          >
            <header className="profile-drawer__header">
              <div>
                <p>Health profile</p>
                <h2 id="profile-drawer-title">Update Health Profile</h2>
              </div>
              <button
                type="button"
                disabled={isSaving}
                onClick={() => setIsEditing(false)}
                aria-label="Close profile editor"
              >
                ×
              </button>
            </header>
            <HealthProfileForm
              key={profile.updated_at}
              profile={profile}
              submitLabel="Save Changes"
              isSaving={isSaving}
              error={error}
              onSubmit={saveAndClose}
              onCancel={() => setIsEditing(false)}
            />
          </aside>
        </div>
      ) : null}
    </main>
  );
}

function PageHeader({ onEdit }: { onEdit?: () => void }) {
  return (
    <header className="health-profile-page__header">
      <div>
        <p>Bitenary / Personal data</p>
        <h1>Health Profile</h1>
      </div>
      {onEdit ? (
        <button type="button" onClick={onEdit}>
          <span aria-hidden="true">✎</span> Edit Profile
        </button>
      ) : null}
    </header>
  );
}

function ProfileStat({
  eyebrow,
  value,
  unit,
  detail,
}: {
  eyebrow: string;
  value: string;
  unit?: string;
  detail: string;
}) {
  return (
    <article className="health-profile-stat">
      <p>{eyebrow}</p>
      <strong>
        {value} {unit ? <small>{unit}</small> : null}
      </strong>
      <span>{detail}</span>
    </article>
  );
}

function ProfileDetail({
  label,
  value,
  description,
}: {
  label: string;
  value: string;
  description: string;
}) {
  return (
    <article className="health-profile-detail">
      <p>{label}</p>
      <strong>{value}</strong>
      <span>{description}</span>
    </article>
  );
}

function PreferenceGroup({
  label,
  type,
  profile,
  tone,
}: {
  label: string;
  type: HealthPreferenceType;
  profile: HealthProfile;
  tone: "danger" | "neutral" | "positive" | "warning";
}) {
  const values = profile.preferences.filter(
    (preference) => preference.preference_type === type,
  );
  return (
    <article className="health-profile-preference">
      <p>{label}</p>
      <div>
        {values.length > 0 ? (
          values.map((preference) => (
            <span
              className={`health-profile-preference__tag health-profile-preference__tag--${tone}`}
              key={preference.value.toLowerCase()}
            >
              {preference.value}
            </span>
          ))
        ) : (
          <span className="health-profile-preference__empty">None specified</span>
        )}
      </div>
    </article>
  );
}

function calculateAge(dateOfBirth: string): number {
  const birthDate = new Date(`${dateOfBirth}T00:00:00`);
  const today = new Date();
  let age = today.getFullYear() - birthDate.getFullYear();
  const monthDifference = today.getMonth() - birthDate.getMonth();
  if (
    monthDifference < 0 ||
    (monthDifference === 0 && today.getDate() < birthDate.getDate())
  ) {
    age -= 1;
  }
  return age;
}

function formatDate(value: string): string {
  return new Intl.DateTimeFormat("en", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  }).format(new Date(value.includes("T") ? value : `${value}T00:00:00`));
}

function formatNumber(value: number): string {
  return new Intl.NumberFormat("en", {
    maximumFractionDigits: 2,
  }).format(value);
}

function activityDescription(level: HealthProfileActivityLevel): string {
  const descriptions: Record<HealthProfileActivityLevel, string> = {
    SEDENTARY: "Little to no intentional exercise.",
    LIGHT: "Approximately 1-2 exercise sessions each week.",
    MODERATE: "Approximately 3-4 exercise sessions each week.",
    ACTIVE: "Approximately 5-6 exercise sessions each week.",
    VERY_ACTIVE: "Daily training or intense physical activity.",
  };
  return descriptions[level];
}
