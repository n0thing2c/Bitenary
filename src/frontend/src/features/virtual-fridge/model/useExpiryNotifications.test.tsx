import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  getNotifications,
  markNotificationRead,
} from "../api/virtualFridgeApi";
import type { ExpiryNotification } from "./types";
import { useExpiryNotifications } from "./useExpiryNotifications";

vi.mock("../api/virtualFridgeApi", () => ({
  getNotifications: vi.fn(),
  markNotificationRead: vi.fn(),
}));

const notification: ExpiryNotification = {
  notification_id: "notification-1",
  fridge_item_id: "fridge-item-1",
  notification_type: "EXPIRING_SOON",
  status: "SENT",
  title: "Pork expires soon",
  message: "Use it within two days.",
  trigger_date: "2026-09-07",
  scheduled_for: "2026-09-07T02:00:00Z",
  sent_at: "2026-09-07T02:00:00Z",
  read_at: null,
  created_at: "2026-09-07T02:00:00Z",
};

const response = {
  items: [notification],
  page: 1,
  size: 20,
  total: 1,
  total_pages: 1,
};

describe("useExpiryNotifications", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(getNotifications).mockResolvedValue(response);
    vi.mocked(markNotificationRead).mockResolvedValue({
      ...notification,
      status: "READ",
      read_at: "2026-09-07T03:00:00Z",
    });
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("does not load notifications for a guest", () => {
    const { result } = renderHook(() => useExpiryNotifications(false));

    expect(getNotifications).not.toHaveBeenCalled();
    expect(result.current.notifications).toEqual([]);
  });

  it("loads unread notifications and removes one after it is read", async () => {
    const { result } = renderHook(() => useExpiryNotifications(true));

    await waitFor(() => expect(result.current.unreadCount).toBe(1));
    await act(async () => result.current.readNotification("notification-1"));

    expect(markNotificationRead).toHaveBeenCalledWith("notification-1");
    expect(result.current.notifications).toEqual([]);
    expect(result.current.unreadCount).toBe(0);
  });

  it("refreshes notifications every 60 seconds", async () => {
    vi.useFakeTimers();
    renderHook(() => useExpiryNotifications(true));

    await act(async () => Promise.resolve());
    expect(getNotifications).toHaveBeenCalledTimes(1);

    await act(async () => vi.advanceTimersByTimeAsync(60_000));
    expect(getNotifications).toHaveBeenCalledTimes(2);
  });

  it("exposes a retry after loading fails", async () => {
    vi.mocked(getNotifications)
      .mockRejectedValueOnce(new Error("offline"))
      .mockResolvedValueOnce(response);
    const { result } = renderHook(() => useExpiryNotifications(true));

    await waitFor(() =>
      expect(result.current.error).toBe("Notifications could not be loaded."),
    );
    await act(async () => result.current.refresh());

    expect(result.current.error).toBeNull();
    expect(result.current.unreadCount).toBe(1);
  });
});
