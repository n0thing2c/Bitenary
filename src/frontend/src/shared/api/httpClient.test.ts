import { afterEach, describe, expect, it, vi } from "vitest";

import { AUTH_EXPIRED_EVENT } from "./authEvents";
import { apiGet, apiPostJson } from "./httpClient";

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function emptyResponse(status: number): Response {
  return new Response(null, { status });
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("HTTP authentication recovery", () => {
  it("returns a successful request without refreshing", async () => {
    const fetchMock = vi.fn().mockResolvedValueOnce(jsonResponse({ ok: true }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(apiGet<{ ok: boolean }>("/api/example")).resolves.toEqual({
      ok: true,
    });
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("refreshes an expired session and retries the request once", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse({ detail: "Not authenticated" }, 401))
      .mockResolvedValueOnce(jsonResponse({ csrf_token: "csrf-token" }))
      .mockResolvedValueOnce(emptyResponse(204))
      .mockResolvedValueOnce(jsonResponse({ ok: true }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(apiGet<{ ok: boolean }>("/api/example")).resolves.toEqual({
      ok: true,
    });

    expect(fetchMock).toHaveBeenCalledTimes(4);
    expect(fetchMock.mock.calls[1][0]).toBe("http://localhost:8000/api/auth/csrf");
    expect(fetchMock.mock.calls[2]).toEqual([
      "http://localhost:8000/api/auth/refresh",
      {
        credentials: "include",
        method: "POST",
        headers: { "X-CSRF-Token": "csrf-token" },
      },
    ]);
    expect(fetchMock.mock.calls[3][0]).toBe("http://localhost:8000/api/example");
  });

  it("shares one refresh across concurrent unauthorized requests", async () => {
    let protectedRequestCount = 0;
    const fetchMock = vi.fn().mockImplementation((input: string | URL | Request) => {
      const url = String(input);
      if (url.endsWith("/api/auth/csrf")) {
        return Promise.resolve(jsonResponse({ csrf_token: "csrf-token" }));
      }
      if (url.endsWith("/api/auth/refresh")) {
        return Promise.resolve(emptyResponse(204));
      }

      protectedRequestCount += 1;
      if (protectedRequestCount <= 2) {
        return Promise.resolve(
          jsonResponse({ detail: "Not authenticated" }, 401),
        );
      }
      return Promise.resolve(jsonResponse({ ok: true }));
    });
    vi.stubGlobal("fetch", fetchMock);

    const [first, second] = await Promise.all([
      apiGet<{ ok: boolean }>("/api/first"),
      apiGet<{ ok: boolean }>("/api/second"),
    ]);

    expect(first).toEqual({ ok: true });
    expect(second).toEqual({ ok: true });
    expect(
      fetchMock.mock.calls.filter(([url]) =>
        String(url).endsWith("/api/auth/refresh"),
      ),
    ).toHaveLength(1);
  });

  it("does not refresh again for a delayed response sent before recovery", async () => {
    let resolveDelayedResponse: ((response: Response) => void) | undefined;
    let firstRequestCount = 0;
    const fetchMock = vi.fn().mockImplementation((input: string | URL | Request) => {
      const url = String(input);
      if (url.endsWith("/api/auth/csrf")) {
        return Promise.resolve(jsonResponse({ csrf_token: "csrf-token" }));
      }
      if (url.endsWith("/api/auth/refresh")) {
        return Promise.resolve(emptyResponse(204));
      }
      if (url.endsWith("/api/first")) {
        firstRequestCount += 1;
        return Promise.resolve(
          firstRequestCount === 1
            ? jsonResponse({ detail: "Not authenticated" }, 401)
            : jsonResponse({ ok: true }),
        );
      }
      if (!resolveDelayedResponse) {
        return new Promise<Response>((resolve) => {
          resolveDelayedResponse = resolve;
        });
      }
      return Promise.resolve(jsonResponse({ ok: true }));
    });
    vi.stubGlobal("fetch", fetchMock);

    const first = apiGet<{ ok: boolean }>("/api/first");
    const delayed = apiGet<{ ok: boolean }>("/api/delayed");
    await expect(first).resolves.toEqual({ ok: true });
    resolveDelayedResponse?.(jsonResponse({ detail: "Not authenticated" }, 401));
    await expect(delayed).resolves.toEqual({ ok: true });

    expect(
      fetchMock.mock.calls.filter(([url]) =>
        String(url).endsWith("/api/auth/refresh"),
      ),
    ).toHaveLength(1);
  });

  it("notifies only once when a shared refresh fails", async () => {
    const listener = vi.fn();
    window.addEventListener(AUTH_EXPIRED_EVENT, listener);
    const fetchMock = vi.fn().mockImplementation((input: string | URL | Request) => {
      const url = String(input);
      if (url.endsWith("/api/auth/csrf")) {
        return Promise.resolve(jsonResponse({ csrf_token: "csrf-token" }));
      }
      if (url.endsWith("/api/auth/refresh")) {
        return Promise.resolve(
          jsonResponse({ detail: "Not authenticated" }, 401),
        );
      }
      return Promise.resolve(jsonResponse({ detail: "Not authenticated" }, 401));
    });
    vi.stubGlobal("fetch", fetchMock);

    const results = await Promise.allSettled([
      apiGet("/api/first"),
      apiGet("/api/second"),
    ]);

    expect(results.every((result) => result.status === "rejected")).toBe(true);
    expect(listener).toHaveBeenCalledTimes(1);
    expect(
      fetchMock.mock.calls.filter(([url]) =>
        String(url).endsWith("/api/auth/refresh"),
      ),
    ).toHaveLength(1);
    window.removeEventListener(AUTH_EXPIRED_EVENT, listener);
  });

  it("notifies the app and does not loop when refresh fails", async () => {
    const listener = vi.fn();
    window.addEventListener(AUTH_EXPIRED_EVENT, listener);
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse({ detail: "Not authenticated" }, 401))
      .mockResolvedValueOnce(jsonResponse({ csrf_token: "csrf-token" }))
      .mockResolvedValueOnce(jsonResponse({ detail: "Not authenticated" }, 401));
    vi.stubGlobal("fetch", fetchMock);

    await expect(apiGet("/api/example")).rejects.toMatchObject({
      status: 401,
    });
    expect(fetchMock).toHaveBeenCalledTimes(3);
    expect(listener).toHaveBeenCalledTimes(1);
    window.removeEventListener(AUTH_EXPIRED_EVENT, listener);
  });

  it("retries only once when the refreshed request is still unauthorized", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse({ detail: "Not authenticated" }, 401))
      .mockResolvedValueOnce(jsonResponse({ csrf_token: "csrf-token" }))
      .mockResolvedValueOnce(emptyResponse(204))
      .mockResolvedValueOnce(jsonResponse({ detail: "Not authenticated" }, 401));
    vi.stubGlobal("fetch", fetchMock);

    await expect(apiGet("/api/example")).rejects.toMatchObject({
      status: 401,
    });
    expect(fetchMock).toHaveBeenCalledTimes(4);
  });

  it("does not auto-refresh excluded authentication endpoints", async () => {
    const paths = [
      "/api/auth/csrf",
      "/api/auth/refresh",
      "/api/auth/login",
      "/api/auth/signup",
      "/api/auth/logout",
    ];
    const fetchMock = vi
      .fn()
      .mockImplementation(() =>
        Promise.resolve(jsonResponse({ detail: "Not authenticated" }, 401)),
      );
    vi.stubGlobal("fetch", fetchMock);

    const results = await Promise.allSettled(paths.map((path) => apiGet(path)));

    expect(results.every((result) => result.status === "rejected")).toBe(true);
    expect(fetchMock).toHaveBeenCalledTimes(paths.length);
  });

  it("sends JSON and CSRF headers for state-changing requests", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse({ client_id: "client" }, 201));
    vi.stubGlobal("fetch", fetchMock);

    await apiPostJson<{ client_id: string }>(
      "/api/mcp-connections",
      { client_type: "CODEX", display_name: "My Codex" },
      "csrf-token",
    );

    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/mcp-connections",
      {
        credentials: "include",
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRF-Token": "csrf-token",
        },
        body: JSON.stringify({
          client_type: "CODEX",
          display_name: "My Codex",
        }),
      },
    );
  });
});
