// Generate typed API definitions from the shared contracts (tasks T009, T201).
// Usage: pnpm gen:api   (writes src/api/schema.ts and src/api/accounts-schema.ts; CI fails if
// either file is out of date)
import { mkdirSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import openapiTS, { astToString } from "openapi-typescript";

const here = dirname(fileURLToPath(import.meta.url));
const outputs = [
  ["specs/001-m1-web-app/contracts/openapi.yaml", "schema.ts"],
  ["specs/002-accounts/contracts/accounts.openapi.yaml", "accounts-schema.ts"],
];

for (const [contract, file] of outputs) {
  const target = resolve(here, "../src/api", file);
  const ast = await openapiTS(pathToFileURL(resolve(here, "../..", contract)));
  const header = `// Generated from ${contract}. Do not edit.\n`;
  mkdirSync(dirname(target), { recursive: true });
  writeFileSync(target, header + astToString(ast));
  console.log(`wrote ${target}`);
}
