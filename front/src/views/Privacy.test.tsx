// FR-035: what is stored, where, and that clearing the browser removes local progress.

import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Privacy } from "./Privacy";

describe("Privacy", () => {
  it("says what is kept, where, and what clearing the browser does", () => {
    render(<Privacy />);
    expect(screen.getByRole("heading", { level: 1, name: "What we keep, and where" })).toBeInTheDocument();
    expect(screen.getByText(/Zurich, Switzerland/)).toBeInTheDocument();
    expect(screen.getByText(/If you clear this site's data/)).toBeInTheDocument();
    expect(screen.getByText(/never your IP address/)).toBeInTheDocument();
    expect(screen.getByText(/daily games: about 90 days/)).toBeInTheDocument();
  });
});
