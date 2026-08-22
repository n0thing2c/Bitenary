import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { redirectToLogin } from "../../auth/api/authApi";
import { useChat } from "../model/useChat";
import { ChatPage } from "./ChatPage";

vi.mock("../../auth/api/authApi", () => ({
  redirectToAccountSettings: vi.fn(),
  redirectToLogin: vi.fn(),
}));

vi.mock("../model/useChat", () => ({
  useChat: vi.fn(),
}));

describe("ChatPage guest limits", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(useChat).mockReturnValue({
      messages: [],
      sessions: [],
      activeSessionId: "guest-session",
      isLoading: false,
      error: "Guest chat limit reached. Sign in to continue.",
      errorStatus: 429,
      switchSession: vi.fn(),
      newSession: vi.fn(),
      sendMessage: vi.fn(),
      dismissError: vi.fn(),
      scrollAnchorRef: { current: null },
    });
  });

  it("offers login when a guest reaches the quota", async () => {
    render(
      <MemoryRouter>
        <ChatPage
          user={null}
          isLoggingOut={false}
          onLogout={vi.fn()}
        />
      </MemoryRouter>,
    );

    await userEvent.click(
      screen.getByRole("button", { name: "Login to continue" }),
    );

    expect(redirectToLogin).toHaveBeenCalledWith("/");
  });
});
