export function TypingIndicator() {
  return (
    <div className="chat-typing" aria-label="Bitenary AI is thinking" aria-live="polite">
      <div className="chat-message__avatar" aria-hidden="true">B</div>
      <div className="chat-typing__dots" aria-hidden="true">
        <span className="chat-typing__dot" />
        <span className="chat-typing__dot" />
        <span className="chat-typing__dot" />
      </div>
    </div>
  );
}
