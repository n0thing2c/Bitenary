import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  createMcpConnection,
  listMcpConnections,
  revokeMcpConnection,
} from "../api/mcpConnectionsApi";
import type {
  CreatedMcpConnection,
  McpConnection,
} from "../model/types";
import { McpConnectionsPanel } from "./McpConnectionsPanel";

vi.mock("../api/mcpConnectionsApi", () => ({
  createMcpConnection: vi.fn(),
  listMcpConnections: vi.fn(),
  revokeMcpConnection: vi.fn(),
}));

const connection: McpConnection = {
  client_id: "178b1991-8b40-471a-9442-6e65ab127638",
  client_type: "CODEX",
  display_name: "My Codex",
  token_prefix: "bty_mcp_a1b2c3d4",
  state: "ACTIVE",
  expires_at: "2026-10-22T00:00:00Z",
  revoked_at: null,
  last_used_at: null,
  created_at: "2026-07-24T00:00:00Z",
};

const createdConnection: CreatedMcpConnection = {
  ...connection,
  mcp_url: "https://api.bitenary.example/mcp",
  token: `bty_mcp_a1b2c3d4.${"s".repeat(43)}`,
  token_env_var: "BITENARY_MCP_TOKEN",
  codex_config:
    '[mcp_servers.bitenary]\nurl = "https://api.bitenary.example/mcp"\nbearer_token_env_var = "BITENARY_MCP_TOKEN"',
  claude_config:
    '{"mcpServers":{"bitenary":{"type":"http","headers":{"Authorization":"Bearer ${BITENARY_MCP_TOKEN}"}}}}',
};

describe("McpConnectionsPanel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(listMcpConnections).mockResolvedValue([]);
    vi.mocked(createMcpConnection).mockResolvedValue(createdConnection);
    vi.mocked(revokeMcpConnection).mockResolvedValue();
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText: vi.fn().mockResolvedValue(undefined) },
    });
  });

  it("renders loading and empty states", async () => {
    render(<McpConnectionsPanel />);

    expect(screen.getByText("Loading connections…")).toBeInTheDocument();
    expect(
      await screen.findByText("No MCP connections yet"),
    ).toBeInTheDocument();
  });

  it("validates the create form", async () => {
    const user = userEvent.setup();
    render(<McpConnectionsPanel />);
    await screen.findByText("No MCP connections yet");

    await user.click(screen.getByRole("button", { name: "New connection" }));
    await user.click(
      screen.getByRole("button", { name: "Create connection" }),
    );

    expect(
      screen.getByText("Display name must contain 1 to 100 characters."),
    ).toBeInTheDocument();
    expect(createMcpConnection).not.toHaveBeenCalled();
  });

  it("creates a connection and displays the token only until dialog close", async () => {
    const user = userEvent.setup();
    const storageSpy = vi.spyOn(Storage.prototype, "setItem");
    render(<McpConnectionsPanel />);
    await screen.findByText("No MCP connections yet");

    await user.click(screen.getByRole("button", { name: "New connection" }));
    await user.selectOptions(screen.getByLabelText("Agent"), "CLAUDE");
    await user.type(screen.getByLabelText("Display name"), "My Claude");
    await user.click(
      screen.getByRole("button", { name: "Create connection" }),
    );

    expect(await screen.findByText("Save your token now")).toBeInTheDocument();
    expect(screen.getByText(createdConnection.token)).toBeInTheDocument();
    expect(createMcpConnection).toHaveBeenCalledWith({
      client_type: "CLAUDE",
      display_name: "My Claude",
    });
    expect(storageSpy).not.toHaveBeenCalled();

    await user.click(screen.getAllByRole("button", { name: "Copy" })[0]);
    expect(screen.getByRole("button", { name: "Copied" })).toBeInTheDocument();

    await user.click(
      screen.getByRole("button", { name: "I saved the token" }),
    );
    expect(screen.queryByText(createdConnection.token)).not.toBeInTheDocument();
  });

  it("cancels and confirms revocation", async () => {
    const user = userEvent.setup();
    vi.mocked(listMcpConnections).mockResolvedValue([connection]);
    render(<McpConnectionsPanel />);

    expect(await screen.findByText("My Codex")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Revoke" }));
    expect(screen.getByText("Revoke My Codex?")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Cancel" }));
    expect(screen.queryByText("Revoke My Codex?")).not.toBeInTheDocument();
    expect(revokeMcpConnection).not.toHaveBeenCalled();

    await user.click(screen.getByRole("button", { name: "Revoke" }));
    await user.click(
      screen.getByRole("button", { name: "Revoke connection" }),
    );
    await waitFor(() =>
      expect(revokeMcpConnection).toHaveBeenCalledWith(connection.client_id),
    );
  });

  it("renders an API error and retries", async () => {
    vi.mocked(listMcpConnections)
      .mockRejectedValueOnce(new Error("network"))
      .mockResolvedValueOnce([]);
    const user = userEvent.setup();
    render(<McpConnectionsPanel />);

    expect(
      await screen.findByText("Could not load MCP connections."),
    ).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Retry" }));

    expect(
      await screen.findByText("No MCP connections yet"),
    ).toBeInTheDocument();
    expect(listMcpConnections).toHaveBeenCalledTimes(2);
  });
});
