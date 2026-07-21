import { AuthShell } from "../../features/auth/ui/AuthShell";
import { LoginCard } from "../../features/auth/ui/LoginCard";
import { SignedInPanel } from "../../features/auth/ui/SignedInPanel";
import { useAuth } from "../../features/auth/model/useAuth";

import "./AuthPage.css";

export function AuthPage() {
  const { user, isLoading, error, logoutUser } = useAuth();

  return (
    <AuthShell>
      {isLoading && !user ? (
        <section className="auth-loading" aria-live="polite">
          Loading
        </section>
      ) : user ? (
        <SignedInPanel
          user={user}
          error={error}
          isLoading={isLoading}
          onLogout={logoutUser}
        />
      ) : (
        <LoginCard />
      )}
    </AuthShell>
  );
}
