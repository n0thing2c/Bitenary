import {
  apiDelete,
  apiGet,
  apiPostJson,
} from "../../../shared/api/httpClient";
import type {
  CreateMcpConnectionInput,
  CreatedMcpConnection,
  McpConnection,
} from "../model/types";

type CsrfResponse = {
  csrf_token: string;
};

async function getCsrfToken(): Promise<string> {
  const response = await apiGet<CsrfResponse>("/api/auth/csrf");
  return response.csrf_token;
}

export function listMcpConnections(): Promise<McpConnection[]> {
  return apiGet<McpConnection[]>("/api/mcp-connections");
}

export async function createMcpConnection(
  input: CreateMcpConnectionInput,
): Promise<CreatedMcpConnection> {
  const csrfToken = await getCsrfToken();
  return apiPostJson<CreatedMcpConnection>(
    "/api/mcp-connections",
    input,
    csrfToken,
  );
}

export async function revokeMcpConnection(clientId: string): Promise<void> {
  const csrfToken = await getCsrfToken();
  return apiDelete(`/api/mcp-connections/${clientId}`, csrfToken);
}
