import type { CurrentUser } from "../model/types";

import "./SignedInPanel.css";

type SignedInPanelProps = {
  user: CurrentUser;
  error: string | null;
  isLoading: boolean;
  onLogout: () => void;
};

export function SignedInPanel({
  user,
  error,
  isLoading,
  onLogout,
}: SignedInPanelProps) {
  return (
    <section className="signed-in-panel" aria-labelledby="signed-in-title">
      <p className="signed-in-panel__eyebrow">Signed in</p>
      <h1 id="signed-in-title" className="signed-in-panel__title">
        {user.username}
      </h1>
      {user.email ? <p className="signed-in-panel__email">{user.email}</p> : null}
      {error ? <p className="signed-in-panel__error">{error}</p> : null}
      <button
        className="signed-in-panel__button"
        type="button"
        disabled={isLoading}
        onClick={onLogout}
      >
        Log out
      </button>
    </section>
  );
}
