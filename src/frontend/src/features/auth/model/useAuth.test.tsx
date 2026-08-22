import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  getCurrentUser,
  logout,
  redirectToEndSession,
} from "../api/authApi";
import { useAuth } from "./useAuth";
import type { CurrentUser } from "./types";

vi.mock("../api/authApi", () => ({
  getCurrentUser: vi.fn(),
  logout: vi.fn(),
  redirectToEndSession: vi.fn(),
}));

const user: CurrentUser = {
  user_id: "user-1",
  authentik_sub: "authentik-user-1",
  username: "Ada",
  email: "ada@example.com",
  status: "ACTIVE",
};

let container: HTMLDivElement;
let root: Root;
let auth: ReturnType<typeof useAuth>;

function Harness() {
  auth = useAuth();
  return null;
}

beforeEach(async () => {
  vi.mocked(getCurrentUser).mockResolvedValue(user);
  container = document.createElement("div");
  document.body.appendChild(container);
  root = createRoot(container);

  await act(async () => {
    root.render(<Harness />);
  });
});

afterEach(() => {
  act(() => root.unmount());
  container.remove();
  vi.clearAllMocks();
});

describe("useAuth logout", () => {
  it("keeps the authenticated user when the logout request fails", async () => {
    vi.mocked(logout).mockRejectedValue(new Error("network failure"));

    await act(async () => {
      await auth.logoutUser();
    });

    expect(auth.user).toEqual(user);
    expect(auth.isLoading).toBe(false);
    expect(auth.error).toBe("Could not log out. Please try again.");
    expect(redirectToEndSession).not.toHaveBeenCalled();
  });

  it("clears local state and starts Authentik end-session after logout", async () => {
    vi.mocked(logout).mockResolvedValue();

    await act(async () => {
      await auth.logoutUser();
    });

    expect(auth.user).toBeNull();
    expect(auth.error).toBeNull();
    expect(redirectToEndSession).toHaveBeenCalledOnce();
  });
});
