// The invented week of changes files under fixtures/changes/, read as the
// site would serve them: path -> parsed JSON.

import { readdirSync, readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { join } from "node:path";

export const FIXTURES = fileURLToPath(new URL("./fixtures/changes/", import.meta.url));

export function loadFixtures() {
  const out = new Map();
  for (const f of readdirSync(FIXTURES).filter(f => f.endsWith(".json")))
    out.set(`/changes/${f}`, JSON.parse(readFileSync(join(FIXTURES, f), "utf8")));
  return out;
}
