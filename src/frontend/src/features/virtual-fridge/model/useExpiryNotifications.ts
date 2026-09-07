import { useCallback, useEffect, useRef, useState } from "react";

import {
  getNotifications,
  markNotificationRead,
} from "../api/virtualFridgeApi";
import type { ExpiryNotification } from "./types";

const REFRESH_INTERVAL_MS = 60_000;

export function useExpiryNotifications(enabled: boolean) {
  const [notifications, setNotifications] = useState<ExpiryNotification[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const requestId = useRef(0);

  const refresh = useCallback(async () => {
    if (!enabled) return;

    const currentRequest = ++requestId.current;
    setIsLoading(true);
    setError(null);
    try {
      const response = await getNotifications();
      if (requestId.current === currentRequest) {
        setNotifications(response.items);
      }
    } catch {
      if (requestId.current === currentRequest) {
        setError("Notifications could not be loaded.");
      }
    } finally {
      if (requestId.current === currentRequest) setIsLoading(false);
    }
  }, [enabled]);

  useEffect(() => {
    if (!enabled) {
      requestId.current += 1;
      setNotifications([]);
      setIsLoading(false);
      setError(null);
      return;
    }

    void refresh();
    const interval = window.setInterval(() => void refresh(), REFRESH_INTERVAL_MS);
    return () => window.clearInterval(interval);
  }, [enabled, refresh]);

  const readNotification = useCallback(async (notificationId: string) => {
    try {
      await markNotificationRead(notificationId);
      requestId.current += 1;
      setNotifications((current) =>
        current.filter((item) => item.notification_id !== notificationId),
      );
      setIsLoading(false);
      setError(null);
    } catch {
      setError("The notification could not be marked as read.");
    }
  }, []);

  return {
    notifications,
    unreadCount: notifications.length,
    isLoading,
    error,
    refresh,
    readNotification,
  };
}
