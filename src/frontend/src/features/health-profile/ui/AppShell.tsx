import type { ReactNode } from "react";
import { NavLink } from "react-router-dom";

import type { CurrentUser } from "../../auth/model/types";

import "./AppShell.css";

type AppShellProps = {
  user: CurrentUser;
  children: ReactNode;
  isLoggingOut: boolean;
  onLogout: () => void;
};

export function AppShell({
  user,
  children,
  isLoggingOut,
  onLogout,
}: AppShellProps) {
  return (
    <div className="app-shell">
      <aside className="app-sidebar">
        <div className="app-sidebar__brand">
          <BrandMark />
          <div>
            <strong>Bitenary</strong>
            <span>Biological data active</span>
          </div>
        </div>

        <nav className="app-sidebar__nav" aria-label="Primary navigation">
          <DisabledNavItem icon="chat" label="Chat" />
          <NavLink
            className={({ isActive }) =>
              `app-sidebar__link${isActive ? " app-sidebar__link--active" : ""}`
            }
            to="/fridge"
          >
            <NavigationIcon name="fridge" />
            <span>Virtual Fridge</span>
          </NavLink>
          <NavLink
            className={({ isActive }) =>
              `app-sidebar__link${isActive ? " app-sidebar__link--active" : ""}`
            }
            to="/profile"
          >
            <NavigationIcon name="profile" />
            <span>Health Profile</span>
          </NavLink>
          <DisabledNavItem icon="settings" label="Settings" />
        </nav>

        <div className="app-sidebar__account">
          <div className="app-sidebar__avatar" aria-hidden="true">
            {user.username.slice(0, 1).toUpperCase()}
          </div>
          <div className="app-sidebar__identity">
            <strong>{user.username}</strong>
            <span>{user.email ?? "User profile"}</span>
          </div>
          <button
            className="app-sidebar__logout"
            type="button"
            disabled={isLoggingOut}
            onClick={onLogout}
            aria-label="Log out"
            title="Log out"
          >
            <NavigationIcon name="logout" />
          </button>
        </div>
      </aside>

      <div className="app-shell__body">
        <header className="app-mobile-header">
          <div className="app-mobile-header__brand">
            <BrandMark />
            <strong>Bitenary</strong>
          </div>
          <button
            className="app-mobile-header__logout"
            type="button"
            disabled={isLoggingOut}
            onClick={onLogout}
          >
            Log out
          </button>
        </header>
        {children}
        <nav className="app-mobile-nav" aria-label="Mobile navigation">
          <span className="app-mobile-nav__item app-mobile-nav__item--disabled">
            <NavigationIcon name="chat" />
            <span>Chat</span>
          </span>
          <NavLink
            className={({ isActive }) =>
              `app-mobile-nav__item${isActive ? " app-mobile-nav__item--active" : ""}`
            }
            to="/fridge"
          >
            <NavigationIcon name="fridge" />
            <span>Fridge</span>
          </NavLink>
          <NavLink
            className={({ isActive }) =>
              `app-mobile-nav__item${isActive ? " app-mobile-nav__item--active" : ""}`
            }
            to="/profile"
          >
            <NavigationIcon name="profile" />
            <span>Profile</span>
          </NavLink>
          <span className="app-mobile-nav__item app-mobile-nav__item--disabled">
            <NavigationIcon name="settings" />
            <span>Settings</span>
          </span>
        </nav>
      </div>
    </div>
  );
}

type NavigationIconName =
  | "chat"
  | "fridge"
  | "profile"
  | "settings"
  | "logout";

function DisabledNavItem({
  icon,
  label,
}: {
  icon: NavigationIconName;
  label: string;
}) {
  return (
    <span className="app-sidebar__link app-sidebar__link--disabled">
      <NavigationIcon name={icon} />
      <span>{label}</span>
      <span className="app-sidebar__soon">Soon</span>
    </span>
  );
}

function BrandMark() {
  return (
    <span className="app-brand-mark" aria-hidden="true">
      <svg viewBox="0 0 32 32">
        <path d="M16 3.5 25.4 26H6.6L16 3.5Zm0 7.9-4.7 11.3h9.4L16 11.4Z" />
        <path d="M16 7.3a3.6 3.6 0 1 0 0 7.2 3.6 3.6 0 0 0 0-7.2Zm0 2.3a1.3 1.3 0 1 1 0 2.6 1.3 1.3 0 0 1 0-2.6Z" />
      </svg>
    </span>
  );
}

function NavigationIcon({ name }: { name: NavigationIconName }) {
  const paths: Record<NavigationIconName, ReactNode> = {
    chat: (
      <path d="M4.5 5.5h15v10h-8l-4.5 3v-3H4.5v-10Z" />
    ),
    fridge: (
      <>
        <rect x="6" y="3.5" width="12" height="17" rx="1.5" />
        <path d="M6 9h12M9 6.5v1M9 12v2" />
      </>
    ),
    profile: (
      <>
        <circle cx="12" cy="8" r="3" />
        <path d="M5.5 20v-2.5a6.5 6.5 0 0 1 13 0V20h-13Z" />
      </>
    ),
    settings: (
      <>
        <circle cx="12" cy="12" r="3" />
        <path d="M12 3.5v2M12 18.5v2M3.5 12h2M18.5 12h2M6 6l1.4 1.4M16.6 16.6 18 18M18 6l-1.4 1.4M7.4 16.6 6 18" />
      </>
    ),
    logout: (
      <>
        <path d="M10 4.5H5.5v15H10M14.5 8l4 4-4 4M8 12h10" />
      </>
    ),
  };

  return (
    <svg
      className="app-navigation-icon"
      viewBox="0 0 24 24"
      aria-hidden="true"
    >
      {paths[name]}
    </svg>
  );
}
