import {
  BrowserRouter,
  Navigate,
  Route,
  Routes,
  useNavigate,
} from "react-router-dom";

import { useAuth } from "../features/auth/model/useAuth";
import type { CurrentUser } from "../features/auth/model/types";
import { useHealthProfile } from "../features/health-profile/model/useHealthProfile";
import type { UpsertHealthProfileRequest } from "../features/health-profile/model/types";
import { AppShell } from "../features/health-profile/ui/AppShell";
import { AuthPage } from "../pages/auth/AuthPage";
import { HealthProfileSetupPage } from "../pages/health-profile-setup/HealthProfileSetupPage";
import { HealthProfilePage } from "../pages/health-profile/HealthProfilePage";
import { VirtualFridgePage } from "../pages/virtual-fridge/VirtualFridgePage";

export function App() {
  const auth = useAuth();

  if (!auth.user) {
    return <AuthPage isLoading={auth.isLoading} error={auth.error} />;
  }

  return (
    <BrowserRouter>
      <AuthenticatedProfileApp
        user={auth.user}
        isLoggingOut={auth.isLoading}
        onLogout={auth.logoutUser}
      />
    </BrowserRouter>
  );
}

function AuthenticatedProfileApp({
  user,
  isLoggingOut,
  onLogout,
}: {
  user: CurrentUser;
  isLoggingOut: boolean;
  onLogout: () => void;
}) {
  const profile = useHealthProfile();

  if (profile.isLoading && !profile.data) {
    return <ProfileLoading />;
  }

  if (!profile.data) {
    return (
      <main className="app-state">
        <div>
          <p>{profile.error}</p>
          <button type="button" onClick={() => void profile.loadProfile()}>
            Try again
          </button>
        </div>
      </main>
    );
  }

  return (
    <ProfileRoutes
      user={user}
      isLoggingOut={isLoggingOut}
      onLogout={onLogout}
      profile={profile}
    />
  );
}

function ProfileRoutes({
  user,
  isLoggingOut,
  onLogout,
  profile,
}: {
  user: CurrentUser;
  isLoggingOut: boolean;
  onLogout: () => void;
  profile: ReturnType<typeof useHealthProfile>;
}) {
  const navigate = useNavigate();
  const data = profile.data;
  if (!data) {
    return null;
  }

  async function saveProfile(values: UpsertHealthProfileRequest) {
    await profile.saveProfile(values);
    navigate("/profile", { replace: true });
  }

  async function skipProfile() {
    await profile.skipOnboarding();
    navigate("/profile", { replace: true });
  }

  const defaultPath =
    data.onboarding_state === "NOT_STARTED" ? "/profile/setup" : "/profile";

  return (
    <Routes>
      <Route path="/" element={<Navigate replace to={defaultPath} />} />
      <Route
        path="/profile/setup"
        element={
          data.onboarding_state === "COMPLETED" ? (
            <Navigate replace to="/profile" />
          ) : (
            <HealthProfileSetupPage
              user={user}
              isSaving={profile.isSaving}
              error={profile.error}
              canSkip={data.onboarding_state === "NOT_STARTED"}
              onSave={saveProfile}
              onSkip={skipProfile}
              onBack={() => navigate("/profile")}
            />
          )
        }
      />
      <Route
        path="/profile"
        element={
          data.onboarding_state === "NOT_STARTED" ? (
            <Navigate replace to="/profile/setup" />
          ) : (
            <AppShell
              user={user}
              isLoggingOut={isLoggingOut}
              onLogout={onLogout}
            >
              <HealthProfilePage
                account={data.account}
                profile={data.health_profile}
                isSaving={profile.isSaving}
                error={profile.error}
                onSave={saveProfile}
              />
            </AppShell>
          )
        }
      />
      <Route
        path="/fridge"
        element={
          data.onboarding_state === "NOT_STARTED" ? (
            <Navigate replace to="/profile/setup" />
          ) : (
            <AppShell
              user={user}
              isLoggingOut={isLoggingOut}
              onLogout={onLogout}
            >
              <VirtualFridgePage />
            </AppShell>
          )
        }
      />
      <Route path="*" element={<Navigate replace to={defaultPath} />} />
    </Routes>
  );
}

function ProfileLoading() {
  return (
    <main className="app-state" aria-live="polite">
      <div>
        <span className="app-state__spinner" aria-hidden="true" />
        <p>Loading your biological profile...</p>
      </div>
    </main>
  );
}
