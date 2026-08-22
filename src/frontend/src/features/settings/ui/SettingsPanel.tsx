import { useEffect, useRef } from "react";

import "./SettingsPanel.css";

type SettingsPanelProps = {
  onClose: () => void;
  onOpenMcpConnections: () => void;
  onChangePassword: () => void;
};

export function SettingsPanel({
  onClose,
  onOpenMcpConnections,
  onChangePassword,
}: SettingsPanelProps) {
  const closeButtonRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    closeButtonRef.current?.focus();

    function closeOnEscape(event: KeyboardEvent) {
      if (event.key === "Escape") {
        onClose();
      }
    }

    window.addEventListener("keydown", closeOnEscape);
    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener("keydown", closeOnEscape);
    };
  }, [onClose]);

  return (
    <div
      className="settings-drawer-backdrop"
      data-testid="settings-backdrop"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) {
          onClose();
        }
      }}
    >
      <aside
        className="settings-drawer"
        role="dialog"
        aria-modal="true"
        aria-labelledby="settings-drawer-title"
      >
        <header className="settings-drawer__header">
          <div>
            <p>Account controls</p>
            <h2 id="settings-drawer-title">Settings</h2>
            <span>Manage connected agents and account security.</span>
          </div>
          <button
            ref={closeButtonRef}
            className="settings-drawer__close"
            type="button"
            aria-label="Close settings"
            onClick={onClose}
          >
            ×
          </button>
        </header>

        <div className="settings-drawer__content">
          <p className="settings-drawer__section-label">Connections & security</p>
          <button
            className="settings-action"
            type="button"
            aria-label="MCP connections"
            onClick={onOpenMcpConnections}
          >
            <span className="settings-action__icon" aria-hidden="true">
              <ConnectionIcon />
            </span>
            <span className="settings-action__copy">
              <strong>MCP connections</strong>
              <small>Create and revoke personal connections for AI agents.</small>
            </span>
            <ChevronIcon />
          </button>

          <button
            className="settings-action"
            type="button"
            aria-label="Change password"
            onClick={onChangePassword}
          >
            <span className="settings-action__icon" aria-hidden="true">
              <LockIcon />
            </span>
            <span className="settings-action__copy">
              <strong>Change password</strong>
              <small>Continue to Authentik to update your credentials.</small>
            </span>
            <ExternalIcon />
          </button>
        </div>

        <footer className="settings-drawer__footer">
          Password and identity settings are securely managed by Authentik.
        </footer>
      </aside>
    </div>
  );
}

function ConnectionIcon() {
  return (
    <svg viewBox="0 0 24 24">
      <path d="M8.5 14.5 15.5 7.5" />
      <path d="M6.3 17.7 4.6 19.4a3.5 3.5 0 0 1-5-5l4-4a3.5 3.5 0 0 1 5 0" transform="translate(2)" />
      <path d="m15.4 13.6 4-4a3.5 3.5 0 0 0-5-5l-1.7 1.7" />
    </svg>
  );
}

function LockIcon() {
  return (
    <svg viewBox="0 0 24 24">
      <rect x="5" y="10" width="14" height="11" rx="2" />
      <path d="M8 10V7a4 4 0 0 1 8 0v3" />
      <circle cx="12" cy="15" r="1" />
    </svg>
  );
}

function ChevronIcon() {
  return (
    <svg className="settings-action__trailing" viewBox="0 0 24 24" aria-hidden="true">
      <path d="m9 18 6-6-6-6" />
    </svg>
  );
}

function ExternalIcon() {
  return (
    <svg className="settings-action__trailing" viewBox="0 0 24 24" aria-hidden="true">
      <path d="M14 5h5v5" />
      <path d="m10 14 9-9" />
      <path d="M19 13v5a1 1 0 0 1-1 1H6a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1h5" />
    </svg>
  );
}
