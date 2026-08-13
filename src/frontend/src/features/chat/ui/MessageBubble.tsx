import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { Message } from "../model/types";

type Props = {
  message: Message;
  username: string;
};

function formatTime(date: Date) {
  return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

export function MessageBubble({ message, username }: Props) {
  const isUser = message.role === "user";

  return (
    <div
      className={`chat-message chat-message--${message.role}`}
      aria-label={isUser ? "Your message" : "Bitenary AI reply"}
    >
      <div className="chat-message__avatar" aria-hidden="true">
        {isUser ? username.slice(0, 1).toUpperCase() : "B"}
      </div>
      <div className="chat-message__body">
        <div className="chat-message__bubble">
          {isUser ? (
            message.content
          ) : (
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              components={{
                // Open links in a new tab for safety
                a: ({ ...props }) => (
                  <a {...props} target="_blank" rel="noopener noreferrer" />
                ),
              }}
            >
              {message.content}
            </ReactMarkdown>
          )}
        </div>
        <time
          className="chat-message__time"
          dateTime={message.createdAt.toISOString()}
        >
          {formatTime(message.createdAt)}
        </time>
      </div>
    </div>
  );
}
