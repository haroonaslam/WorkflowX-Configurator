# Unified PrompterX Canonical Guide Audit

This audit records the schema-v7 source-to-profile mapping. It distinguishes concise runtime **rules** from the fuller model-operating **guides**. Each enabled format owns one `common_rules` and one `common_guide`; each supported generation path owns one `path_rules` and one `path_guide`. Reference-state instructions, global NSFW rules, and exact output contracts remain separate.

The model-facing order is fixed: Common Rules → selected Path Rules → selected NSFW rule (when enabled) → Common Guide → selected Path Guide → selected Reference Usage block → exact Output Contract. Titles, sources, conditions, keys, routing state, and editor labels are never submitted.

## Forward source audit

### MiniMax H3 Official

Authoritative source: `C:\Users\User\Desktop\AntiGravity\minimax_system_prompts\minimax-original-system.md`.

| Source material | Destination | Audit decision |
| --- | --- | --- |
| Prompt-output hygiene; camera-visible/microphone-audible facts | Common Rules | Concise constraints used by every supported MiniMax Official path. |
| Shared three-field writing method; playback chronology; shot/timing decision; five-second fallback; Context Loop; camera construction; `<d>[Language]... </d>` dialogue; screen text; `overall_soundscape`; `non_diegetic_music` | Common Guide | Valid across T2VA, I2VA, FL2VA, L2VA, and the playback section of full-reference generation. Headings remain inside the single guide text. |
| T2VA task overview and text-derived construction | Text to Video Path Guide | No frame-alignment wording is included. |
| I2VA opening behavior and forward development | First Frame Path Guide | The exact opening statement remains in the Output Contract; operating method remains in the guide. |
| FL2VA alignment and causal bridge | First–Last Frame Path Guide | Both boundary roles and duration-aware interpolation are path-specific. |
| L2VA inferred opening and exact landing state | Last Frame Path Guide | Enabled only for MiniMax Official because this authoritative source documents L2VA. |
| Full-reference labels, bounded role assignment, summary prefixes, retention markers, detailed-description method, reference audio/voice ownership | Reference to Video Path Guide | Six-field order and exact field names remain in the Output Contract. |
| Image available/unavailable behavior | Reference Usage | Kept conditional and out of the canonical guides. |
| Adult-path additions | Global NSFW Rules | Stored once by path, never duplicated into the profile guide. |
| Three-field, alignment-opening, and six-field response structures | Output Contracts | Exact path/format contract remains directly editable. |
| Task routing, policy, tool use, API limits, and full examples | Excluded | Not model-facing prompt-writing knowledge; useful example concepts were converted into instructions rather than copied as samples. |

The updated source takes precedence over older commit `16680e3`. The obsolete repeated “without a cut, the same continuous camera take continues…” boilerplate is absent. A later shot is created only for a material camera change or principal-action change; timing uses the supplied duration or five seconds when absent.

### MiniMax H3 Alternate

Authoritative source: `C:\Users\User\Desktop\AntiGravity\minimax_system_prompts\minimax-h3-reference-prompts-system.md`.

| Source material | Destination | Audit decision |
| --- | --- | --- |
| Observable/bounded prompting, stable truth, shot construction, timing, camera, dialogue/audio ownership, finishing direction | Common Rules and Common Guide | Shared concepts are consolidated once in the profile-wide fields. |
| Text-only construction | Text to Video Path Guide | Contains only T2V method. |
| First-frame continuation | First Frame Path Guide | Opening-image authority remains conditional in Reference Usage. |
| First/last bridge | First–Last Frame Path Guide | Boundary and causal-transition method remain path-specific. |
| Omni reference authority map, subject/picture/video/audio syntax, editing and continuation behavior | Reference to Video Path Guide | The bracketed response structure stays in its exact Output Contract. |
| Capability snapshot, upload/file limits, agent workflow, policies, validation implementation, and full pattern examples | Excluded | They do not belong in model-facing prompt-authoring guidance. Example concepts were retained as compact operating instructions. |

The alternate source does not independently document a Last Frame-only path, so that path is not enabled.

### LTX 2.3

Sources: local `ltx-2-3-nsfw-prompting` canonical skill plus the official LTX-2.3 prompting guide.

| Source material | Destination |
| --- | --- |
| Detailed production description; observable acting; chronological action; duration-scaled density; cinematography; lighting; dialogue segmentation; synchronized ambience/music/speech | Common Guide |
| Text-derived scene construction | Text to Video Path Guide |
| Animate forward from the visible opening state and emphasize new motion | First Frame Path Guide |
| Build the smallest coherent progression between two boundaries | First–Last Frame Path Guide |
| Connected/no-reference behavior | Reference Usage |
| Natural prompt response and negative channel | Output Contract |
| Audio-input workflows, runtime controls, sample prompts, policy, and implementation workflow | Excluded |

### WAN 2.2

Source: official `Wan2.2/wan/utils/system_prompt.py` prompt-extension instructions.

| Source material | Destination |
| --- | --- |
| Preserve intent, add compatible cinematic detail, causal temporal/spatial coherence, subject/action/camera/lighting/sound description | Common Guide |
| T2V expansion | Text to Video Path Guide |
| Image animation focused on plausible dynamic content | First Frame Path Guide |
| Boundary-frame transition construction | First–Last Frame Path Guide |
| Examples, language duplicates, and implementation constants | Excluded |

### Image profiles

| Profile | Authoritative source | Common Guide coverage | Path Guide split |
| --- | --- | --- | --- |
| Ideogram 4 | Official Ideogram prompting documentation | Natural-language structure, literal interpretation, subject priority, composition, spatial placement, exact quoted typography, clarity and prompt economy | T2I scene construction; I2I edit/reference preservation |
| SDXL | Stability AI SDXL/prompting documentation | Positive prompt anatomy, concept ordering, compatible modifiers, negative prompting, composition/style/lighting/quality control | T2I construction; I2I preservation and requested edits |
| Qwen-Image | Official Qwen-Image repository and prompt-enhancement instructions | Intent-preserving expansion, subject/scene/camera/style detail, exact text rendering, explicit edit targets, multi-image ownership | T2I enhancement; image-edit instructions |
| FLUX.1 dev | Official BFL FLUX prompting guide | Structured natural language, visual hierarchy, spatial relations, camera, lighting, materials, exact text | T2I construction; image-guided transformation |
| FLUX.2 dev | Official BFL FLUX prompting guide | Complex composition, multi-element relationships, text, camera/material detail, reference-aware editing | T2I construction; multi-reference editing behavior |
| Flux Klein | Official BFL FLUX prompting guide | Compact high-signal natural prompting, unambiguous layout and fidelity | T2I construction; restrained image-guided editing |
| Krea2 | Official Krea2 prompting guide and expansion prompt | Long natural descriptions, aesthetic expansion, composition, texture, quoted text, production specificity | T2I expansion; image-preserving edits |
| Z-Image | Official Tongyi-MAI repository and prompt-enhancement material | Fluent prompt enhancement, identity/count/ownership/spatial coherence, bilingual visible text, style and composition | T2I construction; image editing |

API mechanics, sampling flags, capability marketing, model installation, full examples, and unsupported modes are excluded from all image-profile guides. Json layout schemas remain in the exact JSON contracts rather than being duplicated into natural-language guides.

### JsonX

Sources: the private Unified JsonX preset snapshot, isolated engine contracts, and packaged JsonX instruction templates.

| Material | Destination |
| --- | --- |
| Deep hierarchy, canonical values, open-world fallback, coherence, subjects/interactions/negative semantics | Common Guide |
| Text-derived or image-grounded JsonX construction | Selected Path Guide |
| Adaptive, Template Fill, refinement, natural conversion, JSON/natural repair | JsonX Engine selector-driven guide editors |
| Image, presets, hierarchy depth, framing, and Template Fill conditions | JsonX Engine conditional editors |
| Stage 1, Stage 2, and repair request bodies | JsonX Engine user-template editors |
| Preset/schema/template payload data | Preview only as exact injected data; not duplicated as editable guide prose |

## Reverse payload audit

`tests/test_unified_autoprompter.py` exhaustively assembles every built-in profile × enabled format × supported path × connected/no-image state × negative state × NSFW state. It verifies:

- Common Rules, Common Guide, selected Path Rules, and selected Path Guide each occur once.
- Only the selected path’s NSFW rule, reference-state block, and output contract can appear.
- Other path guides are absent.
- Activated block order matches the seven-step assembly contract.
- UI-only keys, engine/routing metadata, source labels, and titles do not enter the prompt.
- MiniMax Official and Alternate retain their exact contract clauses and updated timing behavior.
- Schema-v6 custom rule edits migrate into v7 while curated guides and Last Frame support are installed.
- Preview uses the same backend assembly result that dispatch uses; JsonX Stage 1 receives the selected canonical blocks while Stage 2 remains preset- and profile-routing-agnostic.

The frontend regression surface additionally verifies that Common and Generation Path pages expose exactly two editors each—one Rules and one Guide—and that all JsonX stage, conditional, repair, and user-template fields are visible through the selector-driven editor.
