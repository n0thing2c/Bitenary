import { useState, useRef, useEffect } from "react";
import { NavLink } from "react-router-dom";
import type { CurrentUser } from "../../features/auth/model/types";
import "../../features/chat/ui/tokens.css";
import "./TopNav.css";

type Props = {
  user: CurrentUser;
  isLoggingOut: boolean;
  onLogout: () => void;
};

export function TopNav({ user, isLoggingOut, onLogout }: Props) {
  const [isMenuOpen, setIsMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setIsMenuOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  return (
    <div className="top-nav-wrapper">
      <header className="top-nav" aria-label="Primary navigation">
        {/* Brand */}
        <div className="top-nav__brand">
          <BrandMark />
          <span className="top-nav__wordmark">Bitenary</span>
        </div>

        {/* Main Links */}
        <nav className="top-nav__links">
          <NavLink
            className={({ isActive }) =>
              `top-nav-item${isActive ? " top-nav-item--active" : ""}`
            }
            to="/"
            end
          >
            Chat
          </NavLink>
          <NavLink
            className={({ isActive }) =>
              `top-nav-item${isActive ? " top-nav-item--active" : ""}`
            }
            to="/fridge"
          >
            Virtual Fridge
          </NavLink>
          <NavLink
            className={({ isActive }) =>
              `top-nav-item${isActive ? " top-nav-item--active" : ""}`
            }
            to="/profile"
          >
            Health Profile
          </NavLink>
        </nav>

        {/* Actions & Profile */}
        <div className="top-nav__actions">
          <button
            className="top-nav__icon-btn"
            aria-label="Notifications"
            title="Notifications"
          >
            <IconBell />
          </button>
          <div className="top-nav__user-menu" ref={menuRef}>
            <button 
              className="top-nav__avatar" 
              aria-expanded={isMenuOpen}
              aria-haspopup="true"
              onClick={() => setIsMenuOpen(!isMenuOpen)}
              title="User menu"
            >
              {user.username.slice(0, 1).toUpperCase()}
            </button>
            
            {isMenuOpen && (
              <div className="top-nav__dropdown">
                <div className="top-nav__dropdown-header">
                  <span className="top-nav__dropdown-name">{user.username}</span>
                  {user.email && <span className="top-nav__dropdown-email">{user.email}</span>}
                </div>
                <div className="top-nav__dropdown-divider"></div>
                <button className="top-nav__dropdown-item" onClick={() => setIsMenuOpen(false)}>
                  Settings
                </button>
                <button 
                  className="top-nav__dropdown-item top-nav__dropdown-item--danger" 
                  onClick={() => {
                    setIsMenuOpen(false);
                    onLogout();
                  }}
                  disabled={isLoggingOut}
                >
                  Log out
                </button>
              </div>
            )}
          </div>
        </div>
      </header>
    </div>
  );
}

function BrandMark() {
  return (
    <span className="top-nav-brand-icon" aria-hidden="true">
      <svg viewBox="0 0 32 32">
        <path d="M16 3.5 25.4 26H6.6L16 3.5Zm0 7.9-4.7 11.3h9.4L16 11.4Z" />
        <path d="M16 7.3a3.6 3.6 0 1 0 0 7.2 3.6 3.6 0 0 0 0-7.2Zm0 2.3a1.3 1.3 0 1 1 0 2.6 1.3 1.3 0 0 1 0-2.6Z" />
      </svg>
    </span>
  );
}

function IconBell() {
  return (
    <svg className="top-nav__icon" viewBox="0 0 24 24" aria-hidden="true">
      <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" />
      <path d="M13.73 21a2 2 0 0 1-3.46 0" />
    </svg>
  );
}
