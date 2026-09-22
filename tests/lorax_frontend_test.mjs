import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const source = readFileSync(new URL("../web/js/lorax.js", import.meta.url), "utf8");

assert.match(source, /const LORA_MANAGER_SCAN_ROUTE = "\/api\/lm\/loras\/scan";/);
assert.match(source, /const LORAX_HASH_ROUTE = "\/workflowx_configurator\/lorax\/hash";/);
assert.match(source, /const LORAX_REMAP_ROUTE = "\/workflowx_configurator\/lorax\/remap";/);
assert.match(source, /async function refreshCatalog\(\) \{[\s\S]*catalogPromise = null;[\s\S]*canonicalItemsPromise = null;[\s\S]*return loadCatalog\(\);/);
assert.match(source, /refresh\.title = "Refresh LoRAs";/);
assert.match(source, /top\.append\(search, strictLabel, refresh, close\);/);
assert.match(source, /refresh\.addEventListener\("click", reloadCatalog\);/);
assert.match(source, /if \(selectedFolder && !allItems\.some\(\(item\) => itemMatchesFolder\(item, selectedFolder\)\)\) selectedFolder = "";/);
assert.match(source, /workflowx-lorax-card\{[^}]*min-height:156px/);
assert.match(source, /workflowx-lorax-filename\{[^}]*overflow-wrap:anywhere/);
assert.match(source, /body\.appendChild\(filename\);[\s\S]*body\.appendChild\(name\);/);
assert.match(source, /replace\(\/\[\^a-z0-9\]\+\/g, ""\) !== "lora"/);
assert.doesNotMatch(source, /const chips = \[item\.base_model, item\.sub_type/);
assert.match(source, /async function ensureItemIdentity\(item\) \{[\s\S]*postJson\(LORAX_HASH_ROUTE/);
assert.match(source, /sha256: itemSha256\(item\),[\s\S]*file_size: itemFileSize\(item\),/);
assert.match(source, /row\.sha256 = normalizeSha256/);
assert.match(source, /async function remapRows\(node\) \{[\s\S]*refreshCatalog\(\)[\s\S]*postJson\(LORAX_REMAP_ROUTE/);
assert.match(source, /const originalSize = node\.size \? \[Number\(node\.size\[0\]\), Number\(node\.size\[1\]\)\] : null;/);
assert.match(source, /node\.size\[0\] = originalSize\[0\];[\s\S]*node\.size\[1\] = originalSize\[1\];/);
assert.match(source, /const tooltip = "Remap moved LoRAs";/);

const remapSource = source.slice(source.indexOf("async function remapRows"), source.indexOf("function nodeWidth"));
assert.doesNotMatch(remapSource, /resizeNode\(|setupNode\(/);

console.log("PASS LoraX frontend tests");
