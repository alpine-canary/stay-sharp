// Campaign source (2026-11): which network a visit came from, read from utm_source on arrival.
// Kept in memory only (no cookie, no storage): a reload loses it, and that is fine. The API
// counts plays, challenges and shares per network as aggregates, never per player.
// The utm parameters are taken off the address, so a copied link does not carry them on.

export const SOURCES = ["linkedin", "x", "hn", "devto"] as const;
export type Source = (typeof SOURCES)[number];

const UTM = ["utm_source", "utm_medium", "utm_campaign", "utm_content", "utm_term"];

export function readSource(search: string): Source | null {
  const value = new URLSearchParams(search).get("utm_source");
  return (SOURCES as readonly string[]).includes(value ?? "") ? (value as Source) : null;
}

interface Where {
  pathname: string;
  search: string;
  hash: string;
}

export function takeSource(where: Where, history: Pick<History, "replaceState">): Source | null {
  const source = readSource(where.search);
  const params = new URLSearchParams(where.search);
  if (!UTM.some((key) => params.has(key))) return source;
  for (const key of UTM) params.delete(key);
  const rest = params.toString();
  history.replaceState(null, "", `${where.pathname}${rest ? `?${rest}` : ""}${where.hash}`);
  return source;
}

let current: Source | null = null;

/** Read once when the app starts. */
export function startCampaign(): void {
  current = takeSource(window.location, window.history);
}

export function campaignSource(): Source | null {
  return current;
}
