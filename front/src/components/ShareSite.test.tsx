import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ShareSite, SITE_PITCH } from "./ShareSite";

describe("ShareSite", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("opens the share sheet with the site address", async () => {
    const share = vi.fn().mockResolvedValue(undefined);
    vi.stubGlobal("navigator", { ...navigator, share });
    render(<ShareSite />);
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Share Stay Sharp" }));
    });
    expect(share).toHaveBeenCalledWith({ title: "Stay Sharp", text: SITE_PITCH, url: `${window.location.origin}/` });
    expect(screen.getByRole("status")).toBeEmptyDOMElement();
  });

  it("copies the link where there is no share sheet", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    vi.stubGlobal("navigator", { ...navigator, share: undefined, clipboard: { writeText } });
    render(<ShareSite />);
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Share Stay Sharp" }));
    });
    expect(writeText).toHaveBeenCalledWith(`${window.location.origin}/`);
    expect(screen.getByRole("status")).toHaveTextContent("Link copied.");
  });

  it("shows the link when nothing else works", async () => {
    vi.stubGlobal("navigator", { ...navigator, share: undefined, clipboard: { writeText: vi.fn().mockRejectedValue(new Error("no")) } });
    render(<ShareSite />);
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Share Stay Sharp" }));
    });
    expect(screen.getByRole("status")).toHaveTextContent(`Copy this link: ${window.location.origin}/`);
  });
});
