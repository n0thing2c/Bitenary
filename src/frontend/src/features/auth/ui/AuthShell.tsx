import type { ReactNode } from "react";

import "./AuthShell.css";

type AuthShellProps = {
  children: ReactNode;
};

export function AuthShell({ children }: AuthShellProps) {
  return (
    <main className="auth-shell">
      <header className="auth-brand" aria-label="Bitenary">
        <div className="auth-brand__mark" aria-hidden="true">
          <svg viewBox="0 0 32 32" role="img">
            <path d="M16 3.5 25.4 26H6.6L16 3.5Zm0 7.9-4.7 11.3h9.4L16 11.4Z" />
            <path d="M16 7.3a3.6 3.6 0 1 0 0 7.2 3.6 3.6 0 0 0 0-7.2Zm0 2.3a1.3 1.3 0 1 1 0 2.6 1.3 1.3 0 0 1 0-2.6Z" />
          </svg>
        </div>
        <div className="auth-brand__text">Bitenary</div>
      </header>
      <p className="auth-shell__tagline">BIOLOGICAL DATA FOR PERFORMANCE</p>
      {children}
    </main>
  );
}
