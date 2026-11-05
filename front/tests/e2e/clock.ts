// The local API's clock file (STAGE=local only, see api/src/staysharp/clock.py).

import { writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

export const CLOCK_FILE = resolve(dirname(fileURLToPath(import.meta.url)), "../../../var/e2e-clock.txt");

/** Set the server time (ISO 8601 with offset), or the real time with null. */
export function setServerTime(iso: string | null): void {
  writeFileSync(CLOCK_FILE, iso ?? "");
}
