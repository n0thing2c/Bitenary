import { Link } from "react-router-dom";

import { McpConnectionsPanel } from "../../features/mcp-connections";

import "./McpConnectionsPage.css";

export function McpConnectionsPage() {
  return (
    <main className="mcp-connections-page">
      <header className="mcp-connections-page__header">
        <div>
          <p>Settings</p>
          <h1>Connected agents</h1>
          <span>
            Manage the personal credentials that let external AI agents use
            your Bitenary tools.
          </span>
        </div>
        <Link to="/">Back to chat</Link>
      </header>
      <div className="mcp-connections-page__content">
        <McpConnectionsPanel />
      </div>
    </main>
  );
}
