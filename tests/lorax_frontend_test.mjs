import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const source = readFileSync(new URL("../web/js/lorax.js", import.meta.url), "utf8");

assert.match(source, /const LORA_MANAGER_SCAN_ROUTE = "\/api\/lm\/loras\/scan";/);
assert.match(source, /async function refreshCatalog\(\) \{[\s\S]*catalogPromise = null;[\s\S]*canonicalItemsPromise = null;[\s\S]*return loadCatalog\(\);/);
assert.match(source, /refresh\.title = "Refresh LoRAs";/);
assert.match(source, /top\.append\(search, strictLabel, refresh, close\);/);
assert.match(source, /refresh\.addEventListener\("click", reloadCatalog\);/);
assert.match(source, /if \(selectedFolder && !allItems\.some\(\(item\) => itemMatchesFolder\(item, selectedFolder\)\)\) selectedFolder = "";/);

console.log("PASS LoraX frontend tests");
