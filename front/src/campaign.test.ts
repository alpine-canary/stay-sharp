import { describe, expect, it, vi } from "vitest";
import { readSource, takeSource } from "./campaign";

describe("campaign source", () => {
  it.each([
    ["?utm_source=linkedin&utm_campaign=launch-2026-11", "linkedin"],
    ["?utm_source=x", "x"],
    ["?utm_source=hn", "hn"],
    ["?utm_source=devto", "devto"],
    ["?utm_source=facebook", null],
    ["?utm_source=LinkedIn", null],
    ["?utm_source=", null],
    ["", null],
  ])("reads %s as %s", (search, expected) => {
    expect(readSource(search)).toBe(expected);
  });

  it("keeps the source in memory and takes the utm parameters off the address", () => {
    const replaceState = vi.fn();
    const where = { pathname: "/play", search: "?utm_source=hn&utm_campaign=launch-2026-11&play=p1", hash: "" };
    expect(takeSource(where, { replaceState })).toBe("hn");
    expect(replaceState).toHaveBeenCalledWith(null, "", "/play?play=p1");
  });

  it("leaves an address without utm parameters alone", () => {
    const replaceState = vi.fn();
    expect(takeSource({ pathname: "/", search: "", hash: "" }, { replaceState })).toBeNull();
    expect(replaceState).not.toHaveBeenCalled();
  });
});
