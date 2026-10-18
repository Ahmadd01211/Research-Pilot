import { afterEach, expect, it, vi } from "vitest";
import { ApiError, mutate } from "../src/lib/api/client";
afterEach(() => vi.unstubAllGlobals());
it("fetches a fresh CSRF token and propagates safe API errors", async () => {
  const mock = vi.fn().mockResolvedValueOnce(Response.json({csrf_token:"synthetic"})).mockResolvedValueOnce(Response.json({detail:"Too many attempts"},{status:429}));
  vi.stubGlobal("fetch",mock);
  await expect(mutate("/auth/login","POST",{email:"r@example.com"})).rejects.toBeInstanceOf(ApiError);
  expect(mock.mock.calls[1][1].headers["x-csrf-token"]).toBe("synthetic");
});
it("accepts successful no-content logout",async()=>{
  vi.stubGlobal("fetch",vi.fn().mockResolvedValueOnce(Response.json({csrf_token:"synthetic"})).mockResolvedValueOnce(new Response(null,{status:204})));
  await expect(mutate("/auth/logout","POST")).resolves.toBeUndefined();
});
