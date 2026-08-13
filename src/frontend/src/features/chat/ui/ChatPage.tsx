import { useState } from "react";
import { NavLink } from "react-router-dom";
import type { CurrentUser } from "../../auth/model/types";
import { useChat } from "../model/useChat";
import { ChatLog } from "./ChatLog";
import { ChatInput } from "./ChatInput";
import { TopNav } from "../../../shared/ui/TopNav";
import "./Chat.css";

type Props = {
  user: CurrentUser;
  isLoggingOut: boolean;
  onLogout: () => void;
};

// ─── Nav icons (inline SVG, no external deps) ─────────────────────────────

function IconChat() {
  return (
    <svg className="chat-nav-item__icon" viewBox="0 0 24 24" aria-hidden="true">
      <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
    </svg>
  );
}

function IconFridge() {
  return (
    <svg className="chat-nav-item__icon" viewBox="0 0 24 24" aria-hidden="true">
      <rect x="5" y="2" width="14" height="20" rx="2" />
      <line x1="5" y1="9" x2="19" y2="9" />
      <line x1="9" y1="5.5" x2="9" y2="7" />
      <line x1="9" y1="12" x2="9" y2="15" />
    </svg>
  );
}

function IconProfile() {
  return (
    <svg className="chat-nav-item__icon" viewBox="0 0 24 24" aria-hidden="true">
      <circle cx="12" cy="8" r="4" />
      <path d="M4 20v-2a8 8 0 0 1 16 0v2" />
    </svg>
  );
}

function IconSettings() {
  return (
    <svg className="chat-nav-item__icon" viewBox="0 0 24 24" aria-hidden="true">
      <circle cx="12" cy="12" r="3" />
      <path d="M12 2v2M12 20v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M2 12h2M20 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42" />
    </svg>
  );
}

function IconLogout() {
  return (
    <svg className="chat-nav-item__icon" viewBox="0 0 24 24" aria-hidden="true">
      <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
      <polyline points="16 17 21 12 16 7" />
      <line x1="21" y1="12" x2="9" y2="12" />
    </svg>
  );
}

function IconBell() {
  return (
    <svg className="chat-nav-item__icon" viewBox="0 0 24 24" aria-hidden="true">
      <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" />
      <path d="M13.73 21a2 2 0 0 1-3.46 0" />
    </svg>
  );
}

function IconPlus() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
      <line x1="12" y1="5" x2="12" y2="19" />
      <line x1="5" y1="12" x2="19" y2="12" />
    </svg>
  );
}

function BrandMark() {
  return (
    <span className="chat-brand-mark" aria-hidden="true">
      <svg viewBox="0 0 32 32">
        <path d="M16 3.5 25.4 26H6.6L16 3.5Zm0 7.9-4.7 11.3h9.4L16 11.4Z" />
        <path d="M16 7.3a3.6 3.6 0 1 0 0 7.2 3.6 3.6 0 0 0 0-7.2Zm0 2.3a1.3 1.3 0 1 1 0 2.6 1.3 1.3 0 0 1 0-2.6Z" />
      </svg>
    </span>
  );
}

// ─── Main export ──────────────────────────────────────────────────────────

export function ChatPage({ user, isLoggingOut, onLogout }: Props) {
  const [isSidebarOpen, setIsSidebarOpen] = useState(true);
  
  const {
    messages,
    sessions,
    activeSessionId,
    switchSession,
    newSession,
    isLoading,
    error,
    sendMessage,
    dismissError,
    scrollAnchorRef,
  } = useChat();

  return (
    <div className="chat-workbench">
      {/* ── Top Navigation (Pill) ── */}
      <TopNav user={user} isLoggingOut={isLoggingOut} onLogout={onLogout} />

      <div className="chat-workbench__body">
        {/* Floating toggle button when sidebar is closed */}
        {!isSidebarOpen && (
          <button
            className="sidebar-toggle-btn sidebar-toggle-btn--floating"
            onClick={() => setIsSidebarOpen(true)}
            title="Open sidebar"
            aria-label="Open sidebar"
          >
            <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <line x1="3" y1="12" x2="21" y2="12"></line>
              <line x1="3" y1="6" x2="21" y2="6"></line>
              <line x1="3" y1="18" x2="21" y2="18"></line>
            </svg>
          </button>
        )}

        {/* ── Chat History Sidebar ── */}
        <aside className={`chat-history-sidebar ${!isSidebarOpen ? "chat-history-sidebar--closed" : ""}`} aria-label="Chat history">
          <div className="chat-history-sidebar__top">
            <button
              className="sidebar-toggle-btn"
              onClick={() => setIsSidebarOpen(false)}
              title="Close sidebar"
              aria-label="Close sidebar"
            >
              <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <line x1="3" y1="12" x2="21" y2="12"></line>
                <line x1="3" y1="6" x2="21" y2="6"></line>
                <line x1="3" y1="18" x2="21" y2="18"></line>
              </svg>
            </button>
            <button
              className="chat-sidebar__new-btn"
              type="button"
              onClick={newSession}
              title="Start a new conversation"
            >
              <IconPlus />
              New conversation
            </button>
          </div>

          <div className="chat-history-list">
            <div className="chat-history-group">
              <span className="chat-history-group-title">Recent Chats</span>
              {sessions.map((s) => (
                <button
                  key={s.session_id}
                  className={`chat-history-item ${
                    s.session_id === activeSessionId
                      ? "chat-history-item--active"
                      : ""
                  }`}
                  onClick={() => switchSession(s.session_id)}
                  title={s.title}
                >
                  {s.title || "New conversation"}
                </button>
              ))}
              {sessions.length === 0 && (
                <div
                  style={{
                    padding: "0 var(--space-2)",
                    fontSize: "var(--text-sm)",
                    color: "var(--color-ink-4)",
                  }}
                >
                  No recent chats
                </div>
              )}
            </div>
          </div>
        </aside>

      {/* ── Main area ── */}
      <main className="chat-main" aria-label="Chat">
        {/* Mobile header */}
        <header className="chat-mobile-header">
          <div className="chat-mobile-header__brand">
            <BrandMark />
            Bitenary
          </div>
          <div className="chat-mobile-header__actions">
            <button
              className="chat-mobile-header__btn"
              type="button"
              disabled={isLoggingOut}
              onClick={onLogout}
            >
              Log out
            </button>
          </div>
        </header>



        {/* Log */}
        <ChatLog
          messages={messages}
          isLoading={isLoading}
          username={user.username}
          scrollAnchorRef={scrollAnchorRef}
          onSuggestion={sendMessage}
        />

        {/* Error banner */}
        {error && (
          <div
            className="chat-error"
            role="alert"
            aria-live="assertive"
            style={{ margin: "0 var(--space-6) var(--space-2)", maxWidth: 720 }}
          >
            <span>{error}</span>
            <button
              className="chat-error__dismiss"
              type="button"
              onClick={dismissError}
              aria-label="Dismiss error"
            >
              ×
            </button>
          </div>
        )}

        {/* Composer */}
        <ChatInput onSend={sendMessage} isLoading={isLoading} />
      </main>
      </div>
    </div>
  );
}
