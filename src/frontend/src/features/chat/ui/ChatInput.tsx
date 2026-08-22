import { useCallback, useEffect, useRef, type KeyboardEvent } from "react";

type Props = {
  onSend: (message: string) => void;
  isLoading: boolean;
};

export function ChatInput({ onSend, isLoading }: Props) {
  const ref = useRef<HTMLTextAreaElement>(null);

  const resize = useCallback(() => {
    const el = ref.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 160)}px`;
  }, []);

  useEffect(() => {
    resize();
  }, [resize]);

  function submit() {
    const el = ref.current;
    if (!el || isLoading) return;
    const value = el.value.trim();
    if (!value) return;
    onSend(value);
    el.value = "";
    el.style.height = "auto";
  }

  function onKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      submit();
    }
  }

  return (
    <div className="chat-composer" role="form" aria-label="Chat input">
      <div className="chat-composer__row">
        <div className="chat-composer__inner">
          <textarea
            ref={ref}
            id="chat-textarea"
            className="chat-composer__textarea"
            placeholder="Ask about nutrition, recipes, or health goals…"
            rows={1}
            disabled={isLoading}
            onInput={resize}
            onKeyDown={onKeyDown}
            aria-label="Message input"
            aria-multiline="true"
          />
          <button
            id="chat-send-btn"
            className="chat-composer__send"
            type="button"
            disabled={isLoading}
            data-state={isLoading ? "loading" : undefined}
            onClick={submit}
            aria-label={isLoading ? "Sending…" : "Send message"}
          >
            {isLoading ? (
              <span className="chat-send-spinner" aria-hidden="true" />
            ) : (
              <svg viewBox="0 0 24 24" aria-hidden="true">
                <line x1="22" y1="2" x2="11" y2="13" />
                <polygon points="22 2 15 22 11 13 2 9 22 2" />
              </svg>
            )}
          </button>
        </div>
        <p className="chat-composer__hint">
          Enter to send · Shift+Enter for new line
        </p>
      </div>
    </div>
  );
}
