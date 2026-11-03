import { render, screen } from "@testing-library/react";
import { App } from "./App";

test("shows the game name as the main heading", () => {
  render(<App />);
  expect(screen.getByRole("heading", { level: 1, name: "Stay Sharp" })).toBeInTheDocument();
});
