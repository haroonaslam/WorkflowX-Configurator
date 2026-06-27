import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const source = readFileSync(new URL("../web/js/lorax_search.js", import.meta.url), "utf8");
const moduleUrl = `data:text/javascript;base64,${Buffer.from(source).toString("base64")}`;
const { itemMatchesQuery } = await import(moduleUrl);

const sdxl = {
  load_name: "SDXL 1.0/concept/Pussy_Lily_v5_XL.safetensors",
  folder: "SDXL 1.0/concept",
  filename: "Pussy_Lily_v5_XL.safetensors",
  file_stem: "Pussy_Lily_v5_XL",
  full_path: "D:/ComfyUI/models/loras/SDXL 1.0/concept/Pussy_Lily_v5_XL.safetensors",
  canonical_display_name: "Pussy_Lily_v5_XL",
  display_name: "Real Pussy - Lily",
  base_model: "SDXL 1.0",
  tags: ["concept"],
  metadata: {
    model_name: "Real Pussy - Lily",
    file_name: "Pussy_Lily_v5_XL",
    folder: "SDXL 1.0/concept",
    file_path: "D:/ComfyUI/models/loras/SDXL 1.0/concept/Pussy_Lily_v5_XL.safetensors",
    base_model: "SDXL 1.0",
  },
};

const kleinWithMultiBaseTitle = {
  load_name: "Flux.2 Klein 9B-base/concept/Labiaplasty Innie Pussy Adjuster.safetensors",
  folder: "Flux.2 Klein 9B-base/concept",
  filename: "Labiaplasty Innie Pussy Adjuster.safetensors",
  file_stem: "Labiaplasty Innie Pussy Adjuster",
  full_path: "D:/ComfyUI/models/loras/Flux.2 Klein 9B-base/concept/Labiaplasty Innie Pussy Adjuster.safetensors",
  canonical_display_name: "Labiaplasty Innie Pussy Adjuster",
  display_name: "Labiaplasty Innie Pussy Adjuster [K9B ZImage SDXL Qwen Chroma SD1]",
  base_model: "Flux.2 Klein 9B-base",
  tags: ["cleft of venus", "concept", "innie"],
  metadata: {
    model_name: "Labiaplasty Innie Pussy Adjuster [K9B ZImage SDXL Qwen Chroma SD1]",
    file_name: "Labiaplasty Innie Pussy Adjuster",
    folder: "Flux.2 Klein 9B-base/concept",
    file_path: "D:/ComfyUI/models/loras/Flux.2 Klein 9B-base/concept/Labiaplasty Innie Pussy Adjuster.safetensors",
    base_model: "Flux.2 Klein 9B-base",
    tags: ["cleft of venus", "concept", "innie"],
  },
};

const zimageWithMultiBaseTitle = {
  ...kleinWithMultiBaseTitle,
  load_name: "ZImageBase/concept/m99_labiaplasty_pussy_6_zimage.safetensors",
  folder: "ZImageBase/concept",
  filename: "m99_labiaplasty_pussy_6_zimage.safetensors",
  file_stem: "m99_labiaplasty_pussy_6_zimage",
  full_path: "D:/ComfyUI/models/loras/ZImageBase/concept/m99_labiaplasty_pussy_6_zimage.safetensors",
  canonical_display_name: "m99_labiaplasty_pussy_6_zimage",
  base_model: "ZImageBase",
  metadata: {
    ...kleinWithMultiBaseTitle.metadata,
    file_name: "m99_labiaplasty_pussy_6_zimage",
    folder: "ZImageBase/concept",
    file_path: "D:/ComfyUI/models/loras/ZImageBase/concept/m99_labiaplasty_pussy_6_zimage.safetensors",
    base_model: "ZImageBase",
  },
};

assert.equal(itemMatchesQuery(sdxl, "pussy sdxl", false), true);
assert.equal(itemMatchesQuery(sdxl, "sdxl pussy", false), true);
assert.equal(itemMatchesQuery(sdxl, "pussy sdxl", true), true);
assert.equal(itemMatchesQuery(sdxl, "sdxl pussy", true), true);

assert.equal(itemMatchesQuery(kleinWithMultiBaseTitle, "pussy sdxl", false), true);
assert.equal(itemMatchesQuery(zimageWithMultiBaseTitle, "pussy sdxl", false), true);

assert.equal(itemMatchesQuery(kleinWithMultiBaseTitle, "pussy sdxl", true), false);
assert.equal(itemMatchesQuery(zimageWithMultiBaseTitle, "pussy sdxl", true), false);
assert.equal(itemMatchesQuery(kleinWithMultiBaseTitle, "sdxl pussy", true), false);
assert.equal(itemMatchesQuery(zimageWithMultiBaseTitle, "sdxl pussy", true), false);

console.log("PASS LoraX search helper tests");
