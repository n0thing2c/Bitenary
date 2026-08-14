import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError, apiGet } from "../../../shared/api/httpClient";
import {
  ChatSession,
  getChatSessionMessages,
  getChatSessions,
  sendGuestMessage,
  sendMessage as apiSendMessage,
} from "../api/chatApi";
import type { Message } from "./types";

type CsrfResponse = { csrf_token: string };

type ChatState = {
  messages: Message[];
  isLoading: boolean;
  error: string | null;
  errorStatus: number | null;
};

function randomId() {
  return Math.random().toString(36).slice(2, 10);
}

export function useChat({ isAuthenticated }: { isAuthenticated: boolean }) {
  const [state, setState] = useState<ChatState>({
    messages: [],
    isLoading: false,
    error: null,
    errorStatus: null,
  });
  
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string>(() => {
    if (!isAuthenticated) return crypto.randomUUID();
    const saved = sessionStorage.getItem("bitenary_chat_session_id");
    if (saved) return saved;
    const newId = crypto.randomUUID();
    sessionStorage.setItem("bitenary_chat_session_id", newId);
    return newId;
  });

  const csrfRef = useRef<string | null>(null);

  // Fetch list of sessions on mount
  useEffect(() => {
    if (!isAuthenticated) {
      setSessions([]);
      return;
    }
    getChatSessions()
      .then(setSessions)
      .catch((err) => console.error("Failed to load sessions", err));
  }, [isAuthenticated]);

  // Fetch messages when activeSessionId changes
  useEffect(() => {
    if (!isAuthenticated) {
      setState({
        messages: [],
        isLoading: false,
        error: null,
        errorStatus: null,
      });
      return;
    }

    setState((prev) => ({
      ...prev,
      isLoading: true,
      error: null,
      errorStatus: null,
    }));
    getChatSessionMessages(activeSessionId)
      .then((msgs) => {
        setState({
          messages: msgs.map((m) => {
            const roleMap: Record<string, "user" | "assistant"> = {
              human: "user",
              ai: "assistant",
            };
            return {
              id: m.id,
              role: roleMap[m.role] || "user",
              content: m.content,
              createdAt: new Date(m.created_at),
            };
          }),
          isLoading: false,
          error: null,
          errorStatus: null,
        });
      })
      .catch((err) => {
        // If API fails or session is new/empty, just start with empty messages
        setState({
          messages: [],
          isLoading: false,
          error: null,
          errorStatus: null,
        });
      });
  }, [activeSessionId, isAuthenticated]);

  // Fetch and cache the CSRF token once
  const getCsrf = useCallback(async (): Promise<string> => {
    if (csrfRef.current) return csrfRef.current;
    const { csrf_token } = await apiGet<CsrfResponse>("/api/auth/csrf");
    csrfRef.current = csrf_token;
    return csrf_token;
  }, []);

  // Optimistically append user message, then await AI reply
  const sendMessage = useCallback(
    async (content: string) => {
      const trimmed = content.trim();
      if (!trimmed || state.isLoading) return;

      const userMsg: Message = {
        id: randomId(),
        role: "user",
        content: trimmed,
        createdAt: new Date(),
      };

      setState((prev) => ({
        messages: [...prev.messages, userMsg],
        isLoading: true,
        error: null,
        errorStatus: null,
      }));

      try {
        const csrf = await getCsrf();
        const send = isAuthenticated ? apiSendMessage : sendGuestMessage;
        const { reply } = await send(trimmed, activeSessionId, csrf);

        const assistantMsg: Message = {
          id: randomId(),
          role: "assistant",
          content: reply,
          createdAt: new Date(),
        };

        setState((prev) => ({
          messages: [...prev.messages, assistantMsg],
          isLoading: false,
          error: null,
          errorStatus: null,
        }));
        
        // Refresh session list so the new title shows up if this was the first message
        if (isAuthenticated && state.messages.length === 0) {
          getChatSessions().then(setSessions).catch(console.error);
        }
      } catch (err) {
        const message =
          err instanceof Error ? err.message : "Something went wrong.";
        setState((prev) => ({
          ...prev,
          isLoading: false,
          error: message,
          errorStatus: err instanceof ApiError ? err.status : null,
        }));
      }
    },
    [
      state.isLoading,
      state.messages.length,
      activeSessionId,
      getCsrf,
      isAuthenticated,
    ],
  );

  const dismissError = useCallback(() => {
    setState((prev) => ({ ...prev, error: null, errorStatus: null }));
  }, []);
  
  const switchSession = useCallback((sessionId: string) => {
    if (isAuthenticated) {
      sessionStorage.setItem("bitenary_chat_session_id", sessionId);
    }
    setActiveSessionId(sessionId);
  }, [isAuthenticated]);
  
  const newSession = useCallback(() => {
    const newId = crypto.randomUUID();
    if (isAuthenticated) {
      sessionStorage.setItem("bitenary_chat_session_id", newId);
    }
    setActiveSessionId(newId);
  }, [isAuthenticated]);

  // Auto-scroll anchor ref – managed by consumers via the returned ref
  const scrollAnchorRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    scrollAnchorRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [state.messages]);

  return {
    ...state,
    sessions,
    activeSessionId,
    sendMessage,
    switchSession,
    newSession,
    dismissError,
    scrollAnchorRef,
  };
}
