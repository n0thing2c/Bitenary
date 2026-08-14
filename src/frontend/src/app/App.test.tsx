import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { useAuth } from "../features/auth/model/useAuth";
import { App } from "./App";

vi.mock("../features/auth/model/useAuth", () => ({
  useAuth: vi.fn(),
}));

let container: HTMLDivElement;
let root: Root;

beforeEach(() => {
  container = document.createElement("div");
  document.body.appendChild(container);
  root = createRoot(container);
});

afterEach(() => {
  act(() => root.unmount());
  container.remove();
  vi.clearAllMocks();
});

describe("App guest entry", () => {
  it("renders guest chat while the current session is loading", async () => {
    vi.mocked(useAuth).mockReturnValue({
      user: null,
      isLoading: true,
      error: null,
      logoutUser: vi.fn(),
    });

    await act(async () => {
      root.render(<App />);
    });

    expect(container.textContent).toContain("Welcome to Bitenary");
    expect(container.textContent).toContain("Login");
  });

  it("keeps unauthenticated visitors on guest chat", async () => {
    vi.mocked(useAuth).mockReturnValue({
      user: null,
      isLoading: false,
      error: null,
      logoutUser: vi.fn(),
    });

    await act(async () => {
      root.render(<App />);
    });

    expect(container.textContent).toContain("Welcome to Bitenary");
    expect(container.textContent).toContain("Login");
    expect(container.textContent).not.toContain("Log out");
  });
});
