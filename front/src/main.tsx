import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App";
import "./index.css";

const root = document.getElementById("root");
if (!root) throw new Error("Missing #root element");

const container = root;
function start() {
  createRoot(container).render(
    <StrictMode>
      <App />
    </StrictMode>,
  );
}

// A prerendered first screen (src/prerender.tsx) is painted before React replaces it: start one
// frame later, after that paint (FR-034). The dev server has no first screen and starts at once.
if (container.hasChildNodes()) requestAnimationFrame(() => setTimeout(start, 0));
else start();
