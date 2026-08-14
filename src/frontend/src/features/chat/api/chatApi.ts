import { apiGet, apiPostJson } from "../../../shared/api/httpClient";

export type MessageRole = "user" | "assistant";

export type ChatMessage = {
  id: string;
  role: MessageRole;
  content: string;
  created_at: string;
};

export type ChatSession = {
  session_id: string;
  title: string;
  updated_at: string;
};

export async function getChatSessions(): Promise<ChatSession[]> {
  return apiGet<ChatSession[]>("/api/chat/sessions");
}

export async function getChatSessionMessages(
  sessionId: string,
): Promise<ChatMessage[]> {
  return apiGet<ChatMessage[]>(`/api/chat/sessions/${sessionId}/messages`);
}

export type SendMessageRequest = {
  session_id: string;
  message: string;
};

export type SendMessageResponse = {
  session_id: string;
  reply: string;
};

export async function sendMessage(
  message: string,
  sessionId: string,
  csrfToken: string,
): Promise<SendMessageResponse> {
  return apiPostJson<SendMessageResponse>(
    "/api/chat",
    { session_id: sessionId, message } satisfies SendMessageRequest,
    csrfToken,
  );
}

export async function sendGuestMessage(
  message: string,
  sessionId: string,
  csrfToken: string,
): Promise<SendMessageResponse> {
  return apiPostJson<SendMessageResponse>(
    "/api/chat/guest",
    { session_id: sessionId, message } satisfies SendMessageRequest,
    csrfToken,
  );
}
