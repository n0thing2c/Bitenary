import type { CurrentUser } from "../../features/auth/model/types";
import type { UpsertHealthProfileRequest } from "../../features/health-profile/model/types";
import { HealthProfileForm } from "../../features/health-profile/ui/HealthProfileForm";

import "./HealthProfileSetupPage.css";

type HealthProfileSetupPageProps = {
  user: CurrentUser;
  isSaving: boolean;
  error: string | null;
  canSkip: boolean;
  onSave: (profile: UpsertHealthProfileRequest) => Promise<void>;
  onSkip: () => Promise<void>;
  onBack: () => void;
};

export function HealthProfileSetupPage({
  user,
  isSaving,
  error,
  canSkip,
  onSave,
  onSkip,
  onBack,
}: HealthProfileSetupPageProps) {
  async function handleSkip() {
    try {
      await onSkip();
    } catch {
      // The feature hook exposes the request error in the shared form.
    }
  }

  return (
    <main className="profile-setup-page">
      <header className="profile-setup-page__brand" aria-label="Bitenary">
        <span className="profile-setup-page__mark" aria-hidden="true">
          <svg viewBox="0 0 32 32">
            <path d="M16 3.5 25.4 26H6.6L16 3.5Zm0 7.9-4.7 11.3h9.4L16 11.4Z" />
            <path d="M16 7.3a3.6 3.6 0 1 0 0 7.2 3.6 3.6 0 0 0 0-7.2Zm0 2.3a1.3 1.3 0 1 1 0 2.6 1.3 1.3 0 0 1 0-2.6Z" />
          </svg>
        </span>
        <strong>Bitenary</strong>
        <span>Biological data for performance</span>
      </header>

      <section className="profile-setup-card" aria-labelledby="profile-setup-title">
        <div className="profile-setup-card__header">
          <div>
            <p>Welcome, {user.username}</p>
            <h1 id="profile-setup-title">Biological Profile</h1>
            <span>
              Initialize your baseline metrics for personalized analysis.
            </span>
          </div>
          <span className="profile-setup-card__status">Private to you</span>
        </div>

        <HealthProfileForm
          submitLabel="Initialize Profile"
          isSaving={isSaving}
          error={error}
          onSubmit={onSave}
        />

        <button
          className="profile-setup-card__skip"
          type="button"
          disabled={isSaving}
          onClick={canSkip ? () => void handleSkip() : onBack}
        >
          {canSkip ? "Skip for now" : "Back to profile"}
        </button>
      </section>

      <p className="profile-setup-page__privacy">
        Your profile is used only to personalize Bitenary&apos;s nutrition
        experience.
      </p>
    </main>
  );
}
