import { AuthShell } from "../../features/auth/ui/AuthShell";
import { LoginCard } from "../../features/auth/ui/LoginCard";

import "./AuthPage.css";

type AuthPageProps = {
  isLoading: boolean;
  error: string | null;
};

export function AuthPage({ isLoading, error }: AuthPageProps) {
  return (
    <AuthShell>
      {isLoading ? (
        <section className="auth-loading" aria-live="polite">
          Loading
        </section>
      ) : (
        <>
          {error ? (
            <p className="auth-page__error" role="alert">
              {error}
            </p>
          ) : null}
          <LoginCard />
        </>
      )}
    </AuthShell>
  );
}
