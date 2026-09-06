import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, useLocation } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { redirectToAccountSettings } from "../../features/auth/api/authApi";
import { redirectToLogin } from "../../features/auth/api/authApi";
import type { CurrentUser } from "../../features/auth/model/types";
import type { ExpiryNotification } from "../../features/virtual-fridge/model/types";
import { useExpiryNotifications } from "../../features/virtual-fridge/model/useExpiryNotifications";
import { TopNav } from "./TopNav";

vi.mock("../../features/auth/api/authApi", () => ({
  redirectToAccountSettings: vi.fn(),
  redirectToLogin: vi.fn(),
}));

vi.mock("../../features/virtual-fridge/model/useExpiryNotifications", () => ({
  useExpiryNotifications: vi.fn(),
}));

const user: CurrentUser = {
  user_id: "user-1",
  authentik_sub: "authentik-user-1",
  username: "Ada",
  email: "ada@example.com",
  status: "ACTIVE",
};

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

const refreshNotifications = vi.fn(async () => undefined);
const readNotification = vi.fn(async () => undefined);

function mockNotifications() {
  vi.mocked(useExpiryNotifications).mockReturnValue({
    notifications: [notification],
    unreadCount: 1,
    isLoading: false,
    error: null,
    refresh: refreshNotifications,
    readNotification,
  });
}

function LocationProbe() {
  const location = useLocation();
  return <span data-testid="location">{location.pathname}{location.search}</span>;
}

function renderTopNav() {
  render(
    <MemoryRouter initialEntries={["/"]}>
      <TopNav user={user} isLoggingOut={false} onLogout={vi.fn()} />
      <LocationProbe />
    </MemoryRouter>,
  );
}

async function openSettings() {
  const browserUser = userEvent.setup();
  await browserUser.click(
    screen.getByRole("button", { name: "User menu for Ada" }),
  );
  await browserUser.click(screen.getByRole("button", { name: "Settings" }));
  return browserUser;
}

describe("TopNav settings", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockNotifications();
  });

  it("opens the drawer and navigates to MCP connections", async () => {
    renderTopNav();
    const browserUser = await openSettings();

    expect(screen.getByRole("dialog", { name: "Settings" })).toBeInTheDocument();
    await browserUser.click(
      screen.getByRole("button", { name: "MCP connections" }),
    );

    expect(screen.getByTestId("location")).toHaveTextContent(
      "/settings/mcp-connections",
    );
    expect(screen.queryByRole("dialog", { name: "Settings" })).not.toBeInTheDocument();
  });

  it("redirects password management to Authentik", async () => {
    renderTopNav();
    const browserUser = await openSettings();

    await browserUser.click(
      screen.getByRole("button", { name: "Change password" }),
    );

    expect(redirectToAccountSettings).toHaveBeenCalledOnce();
  });

  it("returns focus to the avatar after closing", async () => {
    renderTopNav();
    const browserUser = await openSettings();
    await browserUser.click(screen.getByRole("button", { name: "Close settings" }));

    await waitFor(() =>
      expect(
        screen.getByRole("button", { name: "User menu for Ada" }),
      ).toHaveFocus(),
    );
  });

  it("opens notifications below the bell without changing routes", async () => {
    renderTopNav();

    await userEvent.click(screen.getByRole("button", { name: "Notifications" }));

    expect(screen.getByTestId("location")).toHaveTextContent(/^\/$/);
    expect(
      screen.getByRole("dialog", { name: "Expiry notifications" }),
    ).toBeInTheDocument();
    expect(
      screen.getByLabelText("1 unread notifications"),
    ).toHaveTextContent("1");

    await userEvent.click(screen.getByRole("button", { name: /Pork expires soon/ }));
    expect(readNotification).toHaveBeenCalledWith("notification-1");
  });

  it("closes notifications when the user menu opens", async () => {
    renderTopNav();

    await userEvent.click(screen.getByRole("button", { name: "Notifications" }));
    await userEvent.click(screen.getByRole("button", { name: "User menu for Ada" }));

    expect(
      screen.queryByRole("dialog", { name: "Expiry notifications" }),
    ).not.toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Settings" }),
    ).toBeInTheDocument();
  });

  it("closes notifications with Escape and returns focus to the bell", async () => {
    renderTopNav();
    const bell = screen.getByRole("button", { name: "Notifications" });

    await userEvent.click(bell);
    await userEvent.keyboard("{Escape}");

    await waitFor(() => expect(bell).toHaveFocus());
    expect(
      screen.queryByRole("dialog", { name: "Expiry notifications" }),
    ).not.toBeInTheDocument();
  });

  it("closes notifications when clicking outside", async () => {
    renderTopNav();

    await userEvent.click(screen.getByRole("button", { name: "Notifications" }));
    fireEvent.mouseDown(document.body);

    expect(
      screen.queryByRole("dialog", { name: "Expiry notifications" }),
    ).not.toBeInTheDocument();
  });

  it("caps the unread badge at 99+", () => {
    vi.mocked(useExpiryNotifications).mockReturnValue({
      notifications: [notification],
      unreadCount: 100,
      isLoading: false,
      error: null,
      refresh: refreshNotifications,
      readNotification,
    });

    renderTopNav();

    expect(screen.getByLabelText("100 unread notifications")).toHaveTextContent("99+");
  });

  it("allows a failed notification request to be retried", async () => {
    vi.mocked(useExpiryNotifications).mockReturnValue({
      notifications: [],
      unreadCount: 0,
      isLoading: false,
      error: "Notifications could not be loaded.",
      refresh: refreshNotifications,
      readNotification,
    });
    renderTopNav();

    await userEvent.click(screen.getByRole("button", { name: "Notifications" }));
    await userEvent.click(screen.getByRole("button", { name: "Retry" }));

    expect(refreshNotifications).toHaveBeenCalledOnce();
  });
});

describe("TopNav guest navigation", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockNotifications();
  });

  function renderGuestTopNav() {
    render(
      <MemoryRouter initialEntries={["/"]}>
        <TopNav user={null} isLoggingOut={false} onLogout={vi.fn()} />
      </MemoryRouter>,
    );
  }

  it("shows Login without authenticated account actions", async () => {
    renderGuestTopNav();

    expect(screen.getByRole("button", { name: "Login" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /User menu/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Notifications" })).not.toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Login" }));
    expect(redirectToLogin).toHaveBeenCalledWith("/");
  });

  it("requires login and preserves the private destination", async () => {
    renderGuestTopNav();

    await userEvent.click(screen.getByRole("link", { name: "Virtual Fridge" }));
    expect(redirectToLogin).toHaveBeenCalledWith("/fridge");
  });
});
