// The app itself, loaded by main.tsx once the first screen is on screen.

import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App";
import { startCampaign } from "./campaign";

export function start(container: HTMLElement): void {
  startCampaign();
  createRoot(container).render(
    <StrictMode>
      <App />
    </StrictMode>,
  );
}
