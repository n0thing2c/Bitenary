import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, useLocation } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { redirectToAccountSettings } from "../../features/auth/api/authApi";
import type { CurrentUser } from "../../features/auth/model/types";
import { TopNav } from "./TopNav";

vi.mock("../../features/auth/api/authApi", () => ({
  redirectToAccountSettings: vi.fn(),
}));

const user: CurrentUser = {
  user_id: "user-1",
  authentik_sub: "authentik-user-1",
  username: "Ada",
  email: "ada@example.com",
  status: "ACTIVE",
};

function LocationProbe() {
  const location = useLocation();
  return <span data-testid="location">{location.pathname}</span>;
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
});
