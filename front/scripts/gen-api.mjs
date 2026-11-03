// Generate typed API definitions from the shared contract (task T009).
// Usage: pnpm gen:api   (writes src/api/schema.ts; CI fails if the file is out of date)
import { mkdirSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import openapiTS, { astToString } from "openapi-typescript";

const here = dirname(fileURLToPath(import.meta.url));
const contract = resolve(here, "../../specs/001-m1-web-app/contracts/openapi.yaml");
const target = resolve(here, "../src/api/schema.ts");

const ast = await openapiTS(pathToFileURL(contract));
const header = "// Generated from specs/001-m1-web-app/contracts/openapi.yaml. Do not edit.\n";
mkdirSync(dirname(target), { recursive: true });
writeFileSync(target, header + astToString(ast));
console.log(`wrote ${target}`);
