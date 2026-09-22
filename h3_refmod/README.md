# H3 RefMods — saved profiles

These nodes are part of **WorkflowX → Video → H3 Refmod**. A character contains one visual `.safetensors` file, an optional separate audio `.safetensors` file, a profile-aware `.character.json` manifest, and small browsing previews.

## Create a character

1. Open **01 - Create Ref Character**. Connect the full H3 visual VAE, and the H3 audio VAE if your folder contains voice recordings.
2. Select the **Source folder**. Set a recognizable **Display name**, **Prompt alias** and **Descriptor**. For example: display name `Alice – studio`, alias `alice`, descriptor `a woman with short dark hair`. Package name controls the folder/filename; blank uses Display name. Existing packages are never overwritten.
3. Open **Edit source media**. Use thumbnails and playback to identify sources, drag to reorder, exclude unwanted files and edit recording ranges. Time limits apply across recordings in this order. They do not set resolution or FPS.
4. Choose the profiles to save. The default is **1024 short edge** in each of **Picture profiles**, **Video profiles** and **Combined video profiles**. Enable additional sizes only if you expect to use them: they increase creation work and storage. Every included source receives the matching enabled profiles.
5. Run creation. **decoded_image** connects to Preview Image; **created_paths** connects to Inspect H3 Prompt or Assignments. The result report lists ranges, source frames, saved samples, dimensions and omissions. Browse the new package from a character picker.

### What the profile settings do

| Setting | Meaning and starting choice |
|---|---|
| Saved size | **1024 short edge** is the starting choice. The shorter side targets 1024 pixels and the other follows the source proportions. **2048** retains more detail but costs more. **Original size** avoids intentional source resizing. Small borders may be added for H3 alignment. |
| Downsize method | **Lanczos** is the default for photographs. Bicubic is smoother; Area averages detail; Nearest exact suits hard pixel edges. |
| When the source is smaller | **Keep size** avoids enlargement. **Pad to target** adds borders. Enlargement fills more of the requested frame, but does not guarantee recovered detail. An upscale model can invent texture. |
| Upscale model | Appears only for model enlargement. Uses ComfyUI's installed upscale models and tiled processing, with a floating-point Lanczos finish when necessary. A missing model stops creation. |
| Maximum source frames per video | **16 per video** is a compact starting point. Frames are spaced across the selected recording range. **0** uses all frames. This is not FPS: source timing determines the range, and frames are not repeated to fill it. |
| Maximum reference tokens | Optional for each video/combined profile. **0 means no limit.** This limits reference information, not file size or guaranteed GPU memory. |

Every profile is prepared from the original selected media, then encoded with the H3 VAE. Videos are encoded as clips, not as independent photographs. Profiles do not reconstruct one saved profile to create another.

### Combined profiles

The first selected visual sets the shared proportions. **Original size** uses its dimensions, with alignment padding. **Fit whole image** retains the whole source and adds borders; **Crop to fill** can remove edges. The profile's smaller-source setting controls enlargement or padding.

Pictures and clips are encoded independently into this shared canvas. The package stores those compatible entries and a recipe for the full combined selection. Identical encodings can be shared across profiles; the full combined selection does not require a second duplicate copy of every entry.

When a token allowance is exceeded, similar saved video samples are removed first, then survivors are selected evenly. Each clip is compared only within its own boundaries, using the original RefMod similarity threshold of 0.02. Combined budgets reserve every selected picture first. If pictures alone exceed the allowance, creation stops. Pictures are never automatically dropped or resized to fit a budget.

A saved video sample is a unit produced by the video VAE, not one original source frame. Removing samples may change motion or reference coverage. Reports distinguish original frames from retained saved samples and identify omitted sources.

## Choose references for generation

Select a character, then open **Choose references**. These settings belong to this picker and this workflow; they do not edit the package.

| Visual references | What is sent |
|---|---|
| Saved combined video | The full saved combined selection, using its saved canvas and order. |
| Pictures only | The selected saved pictures as separate picture references. |
| Pictures and video clips | The selected pictures and clips as separate references. |
| Build combined video from selected references | Selected compatible entries, arranged in your chosen order and joined in memory as **one video reference**. |

### Defaults and individual choices

**Default picture profile** applies to pictures whose card says **Use default**. **Default video profile** works separately for clips. An explicit profile chosen on a card takes precedence and stays unchanged when the default changes.

The default list includes only profiles shared by all selected sources of that media type. Profiles match by their saved identity/settings, not by output dimensions: an Original-size profile can produce different dimensions for different pictures. Unselected sources do not restrict the defaults.

If no common profile exists, use **Choose profiles individually** and choose a valid profile on each selected card. If changing the selection invalidates a default, Apply stays disabled until you resolve it. No replacement is chosen silently. Each card shows the resolved profile, actual dimensions and exact cost.

Both combined modes use **one combined profile**. There are no per-source size overrides because every constituent must use the same saved canvas. Reordering does not change that canvas. Sources omitted when a combined profile was created cannot be recovered from that profile; select another saved profile or recreate from original media.

### Reduce video cost

The collapsed **Video reference budget** group defaults to **Use all saved video samples**. To reduce cost, choose **Fit video samples to a token budget**. The preview reports retained and omitted samples before Apply. Pictures remain protected; retained encoded values are unchanged. Use a smaller *saved* profile if you want lower resolution.

**Apply** commits the draft. **Cancel** discards selection/profile edits. Each reference mode retains its own selections, order, overrides and budget. Group expansion, window size and preview/text heights are workflow UI state.

## Conditioning and prompts

Generation loads selected encodings without spatial resizing or VAE re-encoding. Runtime combination concatenates selected encoded sequences in memory; it does not create another file.

- **Direct references only** requires no visual VAE for saved characters. The selected encodings go directly to diffusion conditioning.
- **Vision-language + direct references** also decodes the final selected reference to present it to the vision-language encoder. Diffusion still receives the unchanged selected encoding.
- Regular image/video/audio inputs keep native processing and their normal VAE requirements.

Write one scene prompt on **H3 Mod Reference to Video**. Use the character's `@alias`; use `@alice:` before automatically managed dialogue. **Descriptor** identifies the subject, **Retain** describes what to keep, and **Change** describes requested differences. Catalog names and filenames are not character descriptions.

Named image, video and audio references keep their roles, descriptors and associations. For an external character voice, associate the audio node with that character and disable **Use saved voice** on its picker. Keep the words to speak in the main prompt. Voice association is explicit; mentioning an audio tag does not silently reassign it.

Raw references are numbered first, named references next and saved character entries last, with independent picture/video/audio counters. The shared resolved reference plan drives labels, costs and conditioning. **Final prompt sent to H3** and **Reference and voice assignments** are available for inspection.

**Automatic** generation budgeting uses the calculated requirement with no imposed ceiling. **Manual** stops before text encoding if the complete reference cost exceeds your allowance; it does not change selections. Separate reference counts still follow the existing documented-count check. Choose fewer sources or a combined mode if necessary; increasing a token allowance does not resolve a reference-count limit.

## External RefMods and existing packages

Third-party RefMods expose an **External** profile containing their existing encoding and available metadata. Unknown source boundaries are not guessed. Source selection, protected video-budget reduction and runtime subset assembly are unavailable where that information is missing. Existing visual/audio pairing and explicit character details remain supported.

Earlier custom character manifests require recreation from original media for this release. Old workflow settings are not migrated. Existing packages are never deleted or rewritten automatically. Editing character details or pairing a separate saved voice does not rewrite visual tensors.

Thumbnail files are browsing aids. Generation does not substitute thumbnails for saved reference data.

## Validation and limits

See [VALIDATION.md](VALIDATION.md) for checks and remaining quality-evaluation limits. The examples retain Turbo, SLA and preview integration. H3 remains responsible for appearance, motion and voice generation; correct associations cannot guarantee exact identity or voice cloning.

Saved profiles avoid an additional reconstruction cycle. VAE encoding and downscaling are still lossy; Original size does not mean mathematically lossless storage.

Derived from FranckyB's ComfyUI-H3RefMods and Luisacaotica's MiniMax H3 RefMod implementation. Their MIT license and attribution are retained in the bundled source.


## First and last frames

In **H3 Image Reference → Use reference for**, choose **First frame** or **Last frame**, then connect its named-reference output to H3 Mod Reference to Video. Select one image per endpoint. Connect two image-reference nodes for both endpoints. The main node detects the combination automatically; no mode selector is needed.

Endpoint images are resized proportionally and centre-cropped to fill the output dimensions. Check the output aspect ratio: cropping can remove image edges. A full H3 visual VAE is required even with Direct references only. Endpoint images always inform the vision-language encoder. Associated character and Retain/Change controls are hidden for endpoints.

Keep writing `summary`, `detailed_description` (with optional `[Shot N]` markers), `overall_soundscape`, and `non_diegetic_music`. Endpoint-only prompts compile to `integrated_multimodal_description` with native opening/ending alignment. You can author that field directly instead of `detailed_description`, but cannot supply both. Summary text, dialogue and literal `@@` are retained. Optional endpoint tags can be used in your shots; descriptors clarify their meaning.

Ordinary reference roles still work alongside endpoints. They keep their existing numbering and voice associations. Mixed prompts use explicit opening/ending-frame labels and native keyframe conditioning alongside reference conditioning; this is a validated hybrid extension, not a claimed official prompt template. Your chosen model must support the requested conditioning; the nodes never switch checkpoints.

Reference details reports endpoint positions, crop behavior and separate costs. The ending image is anchored to the actual final frame after native frame-count alignment. Manual budgeting includes both ordinary references and endpoints and stops before text encoding if exceeded. To use one image as both an endpoint and a normal reference, connect separate reference nodes.

Example authoring, using endpoint tags `@opening` and `@ending`:

```text
summary:
A quiet room.
detailed_description:
[Shot 1] The camera holds the composition shown in @opening.
[Shot 2] The shot finishes with the composition shown in @ending.
overall_soundscape:
Quiet room ambience.
non_diegetic_music:
None.
```
