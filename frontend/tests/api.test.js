import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError, _resetForTests, api } from "../src/api.js";

function reply(status, body) {
  return Promise.resolve({ status, ok: status >= 200 && status < 300, json: () => Promise.resolve(body) });
}

describe("api client", () => {
  beforeEach(() => {
    _resetForTests();
    globalThis.fetch = vi.fn();
  });
  afterEach(() => vi.restoreAllMocks());

  it("fetches a CSRF token and sends it with state-changing requests", async () => {
    fetch
      .mockReturnValueOnce(reply(200, { csrf_token: "tok-1" }))
      .mockReturnValueOnce(reply(200, { user: { email: "a@example.com" }, csrf_token: "tok-2" }));
    const data = await api.login("a@example.com", "secret-password-1");
    expect(data.user.email).toBe("a@example.com");
    const [url, options] = fetch.mock.calls[1];
    expect(url).toBe("/api/auth/login");
    expect(options.headers["X-CSRF-Token"]).toBe("tok-1");
    expect(options.credentials).toBe("same-origin");
  });

  it("does not send a CSRF header on GET requests", async () => {
    fetch.mockReturnValueOnce(reply(200, { provers: [], max_time_limit: 30 }));
    await api.provers();
    expect(fetch.mock.calls[0][1].headers["X-CSRF-Token"]).toBeUndefined();
  });

  it("refreshes the token once when the server rejects it", async () => {
    fetch
      .mockReturnValueOnce(reply(200, { csrf_token: "old" }))
      .mockReturnValueOnce(reply(403, { error: "csrf_failed", message: "bad token" }))
      .mockReturnValueOnce(reply(200, { csrf_token: "new" }))
      .mockReturnValueOnce(reply(200, { valid: true }));
    expect(await api.validate("fof(a, axiom, p).")).toEqual({ valid: true });
    expect(fetch.mock.calls[3][1].headers["X-CSRF-Token"]).toBe("new");
  });

  it("raises ApiError with the server's message and code", async () => {
    fetch
      .mockReturnValueOnce(reply(200, { csrf_token: "t" }))
      .mockReturnValueOnce(reply(400, { error: "syntax_error", message: "unexpected character", line: 2, column: 5 }));
    const err = await api.validate("bad").catch((e) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect(err.status).toBe(400);
    expect(err.code).toBe("syntax_error");
    expect(err.body.line).toBe(2);
  });

  it("encodes identifiers in URLs", async () => {
    fetch.mockReturnValueOnce(reply(200, {}));
    await api.run("1/../../admin");
    expect(fetch.mock.calls[0][0]).toBe("/api/runs/1%2F..%2F..%2Fadmin");
  });
});
