import type { ExpiryNotification } from "../model/types";

import "./ExpiryNotificationsPopover.css";

type Props = {
  notifications: ExpiryNotification[];
  isLoading: boolean;
  error: string | null;
  onRetry: () => Promise<void>;
  onRead: (notificationId: string) => Promise<void>;
  onClose: () => void;
};

export function ExpiryNotificationsPopover({
  notifications,
  isLoading,
  error,
  onRetry,
  onRead,
  onClose,
}: Props) {
  return (
    <section
      className="expiry-notifications-popover"
      role="dialog"
      aria-label="Expiry notifications"
    >
      <header>
        <div>
          <p>Stability alerts</p>
          <h2>Notifications</h2>
        </div>
        <button type="button" aria-label="Close notifications" onClick={onClose}>
          ×
        </button>
      </header>

      {isLoading && notifications.length === 0 ? (
        <div className="expiry-notifications-popover__status" role="status">
          <span className="expiry-notifications-popover__spinner" />
          <strong>Loading notifications...</strong>
        </div>
      ) : error && notifications.length === 0 ? (
        <div className="expiry-notifications-popover__status" role="alert">
          <NotificationIcon name="warning" />
          <strong>{error}</strong>
          <button type="button" onClick={() => void onRetry()}>
            Retry
          </button>
        </div>
      ) : notifications.length ? (
        <div className="expiry-notifications-popover__list">
          {notifications.map((notification) => (
            <button
              type="button"
              className="is-unread"
              key={notification.notification_id}
              onClick={() => void onRead(notification.notification_id)}
            >
              <span>
                <NotificationIcon
                  name={notification.notification_type === "EXPIRED" ? "warning" : "clock"}
                />
              </span>
              <div>
                <strong>{notification.title}</strong>
                <p>{notification.message}</p>
                <small>{formatRelativeTime(notification.created_at)}</small>
              </div>
            </button>
          ))}
        </div>
      ) : (
        <div className="expiry-notifications-popover__status">
          <NotificationIcon name="bell" />
          <strong>No alerts yet</strong>
          <span>Expiry reminders will appear here.</span>
        </div>
      )}

      {error && notifications.length > 0 ? (
        <div className="expiry-notifications-popover__refresh-error" role="alert">
          <span>{error}</span>
          <button type="button" onClick={() => void onRetry()}>
            Retry
          </button>
        </div>
      ) : null}
    </section>
  );
}

function NotificationIcon({ name }: { name: "bell" | "clock" | "warning" }) {
  const paths = {
    bell: (
      <>
        <path d="M7 10a5 5 0 0 1 10 0c0 5 2 5 2 6H5c0-1 2-1 2-6Z" />
        <path d="M10 19h4" />
      </>
    ),
    clock: (
      <>
        <circle cx="12" cy="12" r="8" />
        <path d="M12 8v5l3 2" />
      </>
    ),
    warning: (
      <>
        <path d="m12 4 9 16H3L12 4Z" />
        <path d="M12 9v5M12 17h.01" />
      </>
    ),
  };
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      {paths[name]}
    </svg>
  );
}

function formatRelativeTime(value: string): string {
  const minutes = Math.round((Date.now() - new Date(value).getTime()) / 60_000);
  if (minutes < 1) return "Just now";
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.round(hours / 24)}d ago`;
}
