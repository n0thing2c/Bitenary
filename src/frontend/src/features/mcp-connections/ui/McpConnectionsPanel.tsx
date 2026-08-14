import { FormEvent, useCallback, useEffect, useState } from "react";

import {
  createMcpConnection,
  listMcpConnections,
  revokeMcpConnection,
} from "../api/mcpConnectionsApi";
import type {
  CreatedMcpConnection,
  McpClientType,
  McpConnection,
} from "../model/types";

import "./McpConnectionsPanel.css";

type CopyTarget = "token" | "codex" | "claude";

function formatDate(value: string | null): string {
  if (!value) {
    return "Never";
  }
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

export function McpConnectionsPanel() {
  const [connections, setConnections] = useState<McpConnection[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [created, setCreated] = useState<CreatedMcpConnection | null>(null);
  const [revokeTarget, setRevokeTarget] = useState<McpConnection | null>(null);

  const loadConnections = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      setConnections(await listMcpConnections());
    } catch {
      setError("Could not load MCP connections.");
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadConnections();
  }, [loadConnections]);

  async function handleCreated(connection: CreatedMcpConnection) {
    setShowCreate(false);
    setCreated(connection);
    await loadConnections();
  }

  async function handleRevoke() {
    if (!revokeTarget) {
      return;
    }
    try {
      await revokeMcpConnection(revokeTarget.client_id);
      setRevokeTarget(null);
      await loadConnections();
    } catch {
      setError("Could not revoke the MCP connection.");
      setRevokeTarget(null);
    }
  }

  return (
    <section className="mcp-panel" aria-labelledby="mcp-panel-title">
      <header className="mcp-panel__header">
        <div>
          <p className="mcp-panel__eyebrow">External agents</p>
          <h2 id="mcp-panel-title">MCP connections</h2>
          <p className="mcp-panel__intro">
            Connect Codex or Claude to your Bitenary tools with a personal token.
          </p>
        </div>
        <button
          className="mcp-button mcp-button--primary"
          type="button"
          onClick={() => setShowCreate(true)}
        >
          New connection
        </button>
      </header>

      {error ? (
        <div className="mcp-panel__error" role="alert">
          <span>{error}</span>
          <button type="button" onClick={() => void loadConnections()}>
            Retry
          </button>
        </div>
      ) : null}

      {isLoading ? (
        <p className="mcp-panel__status" aria-live="polite">
          Loading connections…
        </p>
      ) : connections.length === 0 ? (
        <div className="mcp-empty">
          <div className="mcp-empty__icon" aria-hidden="true">
            ↗
          </div>
          <h3>No MCP connections yet</h3>
          <p>Create a personal connection when you are ready to add an agent.</p>
        </div>
      ) : (
        <ul className="mcp-connection-list">
          {connections.map((connection) => (
            <li className="mcp-connection-card" key={connection.client_id}>
              <div className="mcp-connection-card__top">
                <div>
                  <span className="mcp-connection-card__type">
                    {connection.client_type}
                  </span>
                  <h3>{connection.display_name}</h3>
                </div>
                <span
                  className={`mcp-state mcp-state--${connection.state.toLowerCase()}`}
                >
                  {connection.state}
                </span>
              </div>
              <dl className="mcp-connection-card__details">
                <div>
                  <dt>Token prefix</dt>
                  <dd>{connection.token_prefix}</dd>
                </div>
                <div>
                  <dt>Last used</dt>
                  <dd>{formatDate(connection.last_used_at)}</dd>
                </div>
                <div>
                  <dt>Expires</dt>
                  <dd>{formatDate(connection.expires_at)}</dd>
                </div>
              </dl>
              {connection.state !== "REVOKED" ? (
                <button
                  className="mcp-button mcp-button--danger"
                  type="button"
                  onClick={() => setRevokeTarget(connection)}
                >
                  Revoke
                </button>
              ) : null}
            </li>
          ))}
        </ul>
      )}

      {showCreate ? (
        <CreateConnectionDialog
          onCancel={() => setShowCreate(false)}
          onCreated={(connection) => void handleCreated(connection)}
        />
      ) : null}
      {created ? (
        <TokenDialog connection={created} onClose={() => setCreated(null)} />
      ) : null}
      {revokeTarget ? (
        <ConfirmRevokeDialog
          connection={revokeTarget}
          onCancel={() => setRevokeTarget(null)}
          onConfirm={() => void handleRevoke()}
        />
      ) : null}
    </section>
  );
}

function CreateConnectionDialog({
  onCancel,
  onCreated,
}: {
  onCancel: () => void;
  onCreated: (connection: CreatedMcpConnection) => void;
}) {
  const [clientType, setClientType] = useState<McpClientType>("CODEX");
  const [displayName, setDisplayName] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const normalizedName = displayName.trim();
    if (!normalizedName || normalizedName.length > 100) {
      setError("Display name must contain 1 to 100 characters.");
      return;
    }
    setIsSubmitting(true);
    setError(null);
    try {
      const connection = await createMcpConnection({
        client_type: clientType,
        display_name: normalizedName,
      });
      onCreated(connection);
    } catch {
      setError("Could not create the MCP connection.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className="mcp-dialog-backdrop">
      <section
        className="mcp-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="create-mcp-title"
      >
        <h3 id="create-mcp-title">Create MCP connection</h3>
        <p>Name the agent that will use this personal connection.</p>
        <form onSubmit={(event) => void handleSubmit(event)}>
          <label>
            Agent
            <select
              value={clientType}
              onChange={(event) =>
                setClientType(event.target.value as McpClientType)
              }
            >
              <option value="CODEX">Codex</option>
              <option value="CLAUDE">Claude</option>
            </select>
          </label>
          <label>
            Display name
            <input
              autoFocus
              maxLength={100}
              placeholder="My Codex"
              value={displayName}
              onChange={(event) => setDisplayName(event.target.value)}
            />
          </label>
          {error ? (
            <p className="mcp-dialog__error" role="alert">
              {error}
            </p>
          ) : null}
          <div className="mcp-dialog__actions">
            <button
              className="mcp-button"
              type="button"
              disabled={isSubmitting}
              onClick={onCancel}
            >
              Cancel
            </button>
            <button
              className="mcp-button mcp-button--primary"
              type="submit"
              disabled={isSubmitting}
            >
              {isSubmitting ? "Creating…" : "Create connection"}
            </button>
          </div>
        </form>
      </section>
    </div>
  );
}

function TokenDialog({
  connection,
  onClose,
}: {
  connection: CreatedMcpConnection;
  onClose: () => void;
}) {
  const [copied, setCopied] = useState<CopyTarget | null>(null);

  async function copy(target: CopyTarget, value: string) {
    await navigator.clipboard.writeText(value);
    setCopied(target);
  }

  return (
    <div className="mcp-dialog-backdrop">
      <section
        className="mcp-dialog mcp-dialog--wide"
        role="dialog"
        aria-modal="true"
        aria-labelledby="mcp-token-title"
      >
        <p className="mcp-dialog__success">Connection created</p>
        <h3 id="mcp-token-title">Save your token now</h3>
        <p className="mcp-dialog__warning">
          This token is shown only once. Bitenary cannot recover it after this
          dialog is closed.
        </p>
        <CopyBlock
          label="Personal token"
          value={connection.token}
          copied={copied === "token"}
          onCopy={() => void copy("token", connection.token)}
        />
        <p className="mcp-dialog__env">
          Store it in the <code>{connection.token_env_var}</code> environment
          variable, then use the matching configuration.
        </p>
        <CopyBlock
          label="Codex config.toml"
          value={connection.codex_config}
          copied={copied === "codex"}
          onCopy={() => void copy("codex", connection.codex_config)}
        />
        <CopyBlock
          label="Claude MCP JSON"
          value={connection.claude_config}
          copied={copied === "claude"}
          onCopy={() => void copy("claude", connection.claude_config)}
        />
        <div className="mcp-dialog__actions">
          <button
            className="mcp-button mcp-button--primary"
            type="button"
            onClick={onClose}
          >
            I saved the token
          </button>
        </div>
      </section>
    </div>
  );
}

function CopyBlock({
  label,
  value,
  copied,
  onCopy,
}: {
  label: string;
  value: string;
  copied: boolean;
  onCopy: () => void;
}) {
  return (
    <div className="mcp-copy-block">
      <div className="mcp-copy-block__header">
        <span>{label}</span>
        <button type="button" onClick={onCopy}>
          {copied ? "Copied" : "Copy"}
        </button>
      </div>
      <pre>{value}</pre>
    </div>
  );
}

function ConfirmRevokeDialog({
  connection,
  onCancel,
  onConfirm,
}: {
  connection: McpConnection;
  onCancel: () => void;
  onConfirm: () => void;
}) {
  return (
    <div className="mcp-dialog-backdrop">
      <section
        className="mcp-dialog"
        role="alertdialog"
        aria-modal="true"
        aria-labelledby="revoke-mcp-title"
      >
        <h3 id="revoke-mcp-title">Revoke {connection.display_name}?</h3>
        <p>
          The current token will stop working immediately for new MCP requests.
        </p>
        <div className="mcp-dialog__actions">
          <button className="mcp-button" type="button" onClick={onCancel}>
            Cancel
          </button>
          <button
            className="mcp-button mcp-button--danger-solid"
            type="button"
            onClick={onConfirm}
          >
            Revoke connection
          </button>
        </div>
      </section>
    </div>
  );
}
