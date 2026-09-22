# Saved-profile validation

Validated locally on 17 September 2026, using ComfyUI's installed H3 models and an isolated test server. The user's main ComfyUI server was not restarted.

## Automated checks

- **33 backend tests passed.** Profile creation, floating-point resizing methods, Original-size alignment padding, native model-upscale adapter, independent defaults and overrides, no-common-profile handling, unavailable defaults, profile omissions, atomic failures, External loading, old custom-format rejection, source-frame caps including unlimited, similarity reduction and picture protection.
- Exact encoded-value equality was checked for selected separate references and runtime concatenation. Direct-only saved generation needs no visual VAE. Native regular image/video/paired-audio conditioning parity passed.
- Prompt tests cover alias conflicts, dialogue protection, speaker numbering, reference numbering, unknown tags and avoiding filename/catalog leakage into the prompt.
- **89 WorkflowX frontend tests passed**, including the shared H3 UI-state checks and unrelated image/audio/video, reference-routing, configuration and LoRA interfaces.
- Browser checks passed for profile defaults/overrides, exact token preview, Apply/Cancel, workflow reload, mode isolation, narrow layouts, source previews, collapsible groups, custom-size/model conditional controls and creation settings.

Backend command, from WorkflowX:

```powershell
& <ComfyUI Python> h3_refmod/tests/run_tests.py --comfy-root <ComfyUI root>
node --test tests/*test*.mjs
```

## Native runtime checks

- Created a real package with two picture profiles, two video profiles and two combined profiles using the full H3 visual VAE, with a separate encoded voice file.
- Ran four short, matched-seed generation diagnostics: separate pictures at 128 with direct conditioning, separate pictures at 256 with vision-language conditioning, and the same runtime combined 256 selection in both conditioning modes. All completed. The first two vary both profile and conditioning, so they do **not** establish a causal quality comparison of profile sizes.
- Loaded and executed both revised example workflows successfully. The creation example used the default 1024 profiles. The generation example retained Turbo, SLA and preview; an old implicit duration relay was replaced with a direct frame-count connection.
- Ran real tiled **4x-UltraSharp** enlargement and the floating-point Lanczos finish, checking final aligned dimensions and finite output.
- Confirmed all **19 files** in the existing Shumaila_d package match their earlier SHA-256 hashes. Package and audio preservation are also covered in backend checks. No original user package was overwritten or deleted.

## Quality observations and limits

The four short diagnostic videos show a consistent face and hair across sampled beginning/middle/end frames, with changing mouth expressions and modest head movement. The two combined-mode samples look very similar in those inspected frames. This is a visual smoke test, not an identity benchmark or a motion-preservation guarantee.

Voice-reference handling and unchanged encoded values were checked. Voice similarity, intelligibility and distortion have not been scored by a listening panel. No improvement in H3's underlying cloning ability is claimed.

Large multi-profile packages, every installed upscale model, and arbitrary third-party file variants have not all been stress-tested. Unsupported formats and missing source boundaries fail or restrict controls explicitly. Runtime selection does not spatially resize or re-encode; creation and VAE encoding remain lossy.

Graphify's tracked code index was refreshed. H3 files are currently untracked in this working tree, so the tracked-scope index does not provide complete H3 coverage; source and runtime checks were used directly.


## First / last frames — 2026-09-18

- 46 backend tests pass, including unchanged reference-only compilation, endpoint cardinality/duplicate errors, first/last/both native conditioning parity, full-VAE requirements, crop/value checks, budget rejection before text encoding, dialogue/escape preservation, and native tokenizer presentation order.
- Mixed saved profiles plus endpoints are tested in both saved-character conditioning modes. Selected saved encodings and original package bytes remain identical. One text-encoding call is asserted. Native PackedLayout ordering is checked against keyframes followed by ordinary reference blocks.
- 9 existing frontend state tests pass. A separate live browser verifies endpoint-only conditional fields and role restoration through workflow serialization/reload. Live resolve diagnostics verify separate endpoint estimates, native final-frame timing and exclusion from ordinary picture counts.
- Real generation succeeded on the installed hybrid FL2VA/Ref2VA b20–49 INT8 model with Turbo, SLA and preview retained: first-frame only, first-frame plus a named scene, and first+last plus a named scene. A matched first-frame run through the native H3 node produced exactly identical decoded video frames (mean absolute pixel difference 0).
- Visual inspection of beginning/middle/end samples shows the cafe composition and recognizable faces retained, with modest head/expression movement. The hybrid sample differs in pose and expression, as expected when adding another reference. These short samples do not establish a general identity/motion benchmark or exact endpoint pixel reproduction.
- Audio generation completed through the existing audiovisual path. Subjective audio quality and voice similarity were not evaluated. GPU tests did not cover every checkpoint or every saved-character/voice combination; those data-preservation paths also have automated coverage.
- No user checkpoint settings or RefMod packages were changed. New optional endpoint nodes and guidance were added to the supplied generation example without connecting them by default.
- Graphify tracked-scope refresh completed, retaining its existing five-edge warning; the semantic update found no changed tracked files. H3 files remain untracked and outside that index.
