export type McpClientType = "CODEX" | "CLAUDE";
export type McpConnectionState =
  | "ACTIVE"
  | "EXPIRED"
  | "REVOKED"
  | "DISABLED";

export type McpConnection = {
  client_id: string;
  client_type: McpClientType;
  display_name: string;
  token_prefix: string;
  state: McpConnectionState;
  expires_at: string;
  revoked_at: string | null;
  last_used_at: string | null;
  created_at: string;
};

export type CreateMcpConnectionInput = {
  client_type: McpClientType;
  display_name: string;
};

export type CreatedMcpConnection = McpConnection & {
  mcp_url: string;
  token: string;
  token_env_var: string;
  codex_config: string;
  claude_config: string;
};
