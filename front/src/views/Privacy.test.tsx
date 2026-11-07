// FR-035: what is stored, where, and that clearing the browser removes local progress.

import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Privacy } from "./Privacy";

describe("Privacy", () => {
  it("says what is kept, where, and what clearing the browser does", () => {
    render(<Privacy />);
    expect(screen.getByRole("heading", { level: 1, name: "What we keep, and where" })).toBeInTheDocument();
    expect(screen.getAllByText(/Zurich, Switzerland/).length).toBeGreaterThan(0);
    expect(screen.getByText(/If you clear this site's data/)).toBeInTheDocument();
    expect(screen.getByText(/never your IP address/)).toBeInTheDocument();
    expect(screen.getByText(/daily games: about 90 days/)).toBeInTheDocument();
  });

  it("says what an account keeps, where, and how to delete it (T235)", () => {
    render(<Privacy />);
    expect(screen.getByRole("heading", { level: 2, name: "If you create an account" })).toBeInTheDocument();
    expect(screen.getByText(/only for players aged 16 and over/)).toBeInTheDocument();
    expect(screen.getByText(/your e-mail address, used only to send you sign-in codes/)).toBeInTheDocument();
    expect(screen.getByText(/deletes all of it within a minute/)).toBeInTheDocument();
    expect(screen.getByText(/Backups keep a copy for up to 35 days/)).toBeInTheDocument();
  });

  it("says when an unused account or address is deleted (FR-120, T243)", () => {
    render(<Privacy />);
    expect(screen.getByText(/do not use your account for two years/)).toBeInTheDocument();
    expect(screen.getByText(/delete your e-mail address after 7 days/)).toBeInTheDocument();
  });
});
