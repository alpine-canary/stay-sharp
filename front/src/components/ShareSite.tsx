// "Share Stay Sharp" in the footer: the phone's share sheet with the site address, or a copied
// link where the browser has no share sheet. Sends nothing anywhere by itself.

import { useState } from "react";
import { canShare } from "./ShareCard";

export const SITE_PITCH = "Five questions a day, with an explanation after each answer.";

export function ShareSite() {
  const [status, setStatus] = useState<string>("");

  async function share() {
    const url = `${window.location.origin}/`;
    setStatus("");
    if (canShare()) {
      try {
        await navigator.share({ title: "Stay Sharp", text: SITE_PITCH, url });
        return;
      } catch (error) {
        if (error instanceof DOMException && error.name === "AbortError") return;
      }
    }
    try {
      await navigator.clipboard.writeText(url);
      setStatus("Link copied.");
    } catch {
      setStatus(`Copy this link: ${url}`);
    }
  }

  return (
    <span className="share-site">
      <button type="button" className="link-btn" onClick={() => void share()}>
        Share Stay Sharp
      </button>
      <span role="status" className="hint">
        {status}
      </span>
    </span>
  );
}
