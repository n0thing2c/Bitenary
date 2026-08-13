import type { RefObject } from "react";
import type { Message } from "../model/types";
import { MessageBubble } from "./MessageBubble";
import { TypingIndicator } from "./TypingIndicator";

const SUGGESTIONS = [
  "Nutrition facts for a bowl of rice?",
  "Suggest a meal plan for the week",
  "What should I eat after the gym?",
  "Low-calorie recipe ideas",
];

type Props = {
  messages: Message[];
  isLoading: boolean;
  username: string;
  scrollAnchorRef: RefObject<HTMLDivElement | null>;
  onSuggestion: (text: string) => void;
};

function EmptyState({ onSuggestion }: { onSuggestion: (t: string) => void }) {
  return (
    <div className="chat-empty">
      <div className="chat-empty__icon" aria-hidden="true">
        <svg viewBox="0 0 24 24">
          <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
        </svg>
      </div>
      <h1 className="chat-empty__heading">Welcome to Bitenary</h1>
      <p className="chat-empty__sub">
        Ask me about nutrition, meal planning, or anything
        related to your health and wellness goals.
      </p>
      <div className="chat-empty__suggestions" aria-label="Suggested prompts">
        {SUGGESTIONS.map((s) => (
          <button
            key={s}
            className="chat-empty__chip"
            type="button"
            onClick={() => onSuggestion(s)}
          >
            {s}
          </button>
        ))}
      </div>
    </div>
  );
}

export function ChatLog({
  messages,
  isLoading,
  username,
  scrollAnchorRef,
  onSuggestion,
}: Props) {
  const hasMessages = messages.length > 0;

  return (
    <div
      className="chat-log"
      role="log"
      aria-label="Conversation"
      aria-live="polite"
    >
      {!hasMessages && !isLoading ? (
        <EmptyState onSuggestion={onSuggestion} />
      ) : (
        <div className="chat-messages">
          {messages.map((msg) => (
            <MessageBubble key={msg.id} message={msg} username={username} />
          ))}
          {isLoading && <TypingIndicator />}
          <div ref={scrollAnchorRef} aria-hidden="true" />
        </div>
      )}
    </div>
  );
}
