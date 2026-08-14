import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { apiGet } from "../../../shared/api/httpClient";
import {
  getChatSessionMessages,
  getChatSessions,
  sendGuestMessage,
  sendMessage,
} from "../api/chatApi";
import { useChat } from "./useChat";

vi.mock("../../../shared/api/httpClient", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../../../shared/api/httpClient")>();
  return { ...actual, apiGet: vi.fn() };
});

vi.mock("../api/chatApi", () => ({
  getChatSessionMessages: vi.fn(),
  getChatSessions: vi.fn(),
  sendGuestMessage: vi.fn(),
  sendMessage: vi.fn(),
}));

describe("useChat guest mode", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(apiGet).mockResolvedValue({ csrf_token: "csrf-token" });
    vi.mocked(sendGuestMessage).mockResolvedValue({
      session_id: "guest-session",
      reply: "Guest reply",
    });
  });

  it("uses the guest endpoint without loading account history", async () => {
    const { result } = renderHook(() => useChat({ isAuthenticated: false }));

    await act(async () => {
      await result.current.sendMessage("Plan a healthy dinner");
    });

    expect(getChatSessions).not.toHaveBeenCalled();
    expect(getChatSessionMessages).not.toHaveBeenCalled();
    expect(sendMessage).not.toHaveBeenCalled();
    expect(sendGuestMessage).toHaveBeenCalledWith(
      "Plan a healthy dinner",
      expect.any(String),
      "csrf-token",
    );
    expect(result.current.messages.map((message) => message.content)).toEqual([
      "Plan a healthy dinner",
      "Guest reply",
    ]);
  });

  it("starts an empty session after remount", async () => {
    const first = renderHook(() => useChat({ isAuthenticated: false }));
    const firstSessionId = first.result.current.activeSessionId;

    await act(async () => {
      await first.result.current.sendMessage("Hello");
    });
    await waitFor(() => expect(first.result.current.messages).toHaveLength(2));
    first.unmount();

    const second = renderHook(() => useChat({ isAuthenticated: false }));
    expect(second.result.current.activeSessionId).not.toBe(firstSessionId);
    expect(second.result.current.messages).toEqual([]);
  });
});
