# MiniMax H3 Official Reference to Video

When a model-facing choice depends on supplied media, choose one definitive value that best fits the brief and references. Do not repeat the entire reference map inside later-shot Context Loops.

## Choose The Output Structure

Use the smallest original MiniMax structure that fits the task:

- **Base original format** for text-only prompts and simple keyframe tasks: output `integrated_multimodal_description`, `overall_soundscape`, and `non_diegetic_music`.
- **Full-reference original format** when image, video, or audio references define identity, scene, style, action, motion, voice, audio, edit source, or reusable subject roles: output `subject_definitions`, `summary`, `retention_analysis`, `detailed_description`, `overall_soundscape`, and `non_diegetic_music`.

For a single image reference that mainly provides the starting visual state, use the base I2VA-style original format by default. Refer to the image as `<Picture 1>` and describe how the video develops forward from it inside `integrated_multimodal_description`. Do not switch to full-reference mode merely because the image contains both a person and an environment.

Prefer full-reference format only when reference roles must be tracked separately, such as multi-reference work, audio reference, motion transfer, targeted editing, voice transfer, character continuity across several assets, storyboard/keyframe planning across multiple pictures, or user-requested full-reference rewriting. Treat an audio, image, or video reference mentioned by the user for this same generation request as an available reference role when its media type and order are unambiguous; include its exact tag, such as `<Audio 1>`, in the prompt.

## Full-Reference Rules

For full-reference prompts:

- Define reusable people, characters, animals, primary objects, and independently controlled visible assets as `<Subject N>`.
- Do not define a background or environment from the same single picture as a separate `<Subject N>` when it is only context to maintain. Instead, cite it as environmental and composition detail from `<Picture N>` inside the relevant shot descriptions.
- Preserve the actual primary subject tightly. Keep the environment coherent with the source image through room type, layout, lighting, and key fixtures, while allowing natural changes caused by camera movement, subject movement, occlusion, focus, and reframing.
- Define an environment as `<Subject N>` only when it is a separate environment reference, the user explicitly asks to reuse or alter the environment independently, no person/object subject is present, or the environment is the primary referenced content.
- When a separate input reference contains only an environment, reference it as `<Picture N>` when it acts as a concrete frame or storyboard anchor, or as `<Subject N>` when the environment itself is reusable visible content across shots. Choose the label role that matches how the reference is used.
- Use `<Picture N>` only when a reference image is a concrete frame anchor or storyboard anchor.
- Use `<Video N>` only for a source video, continuation source, or whole-video structure.
- Use `<Audio N>` only for standalone audio reuse or audio reference.
- Use only reference tags genuinely available to the request. Treat a reference as available when it is already attached, supplied with the request, or mentioned by the user as a reference role for the same generation request and its media type and order are unambiguous. If the user mentions an audio reference and no other audio references are in play, bind it as `<Audio 1>`. Never invent unavailable tags from vague intent, filenames, visible library labels, symbols, or UUIDs. If reference order is ambiguous, ask a concise clarification before writing the final prompt.
- Keep label meanings stable across every section.
- Use the exact retention markers: `fully_preserved`, `partially_preserved`, `attribute_transfer`, `weak_reference`, `fully_copy`, `partially_copy`, and `reference`.
- In `detailed_description`, cite labels where they first appear and where their role applies.
- For every referenced subject or asset, state both what it controls and what it must not contribute. A subject reference does not implicitly control pose, action, expression, framing, background, environment, lighting, camera, text, audio, surrounding people, or unrelated objects. A motion or camera reference does not contribute its actors, identities, bodies, wardrobe, location, props, dialogue, sound, or visual style unless explicitly assigned.
- Write `detailed_description` in playback order with explicit visible composition, referenced subjects and current positions, environment and lighting, observable action and result, camera behavior, synchronized sound, and the exact point where each reference takes effect.

For a single-picture full-reference output, usually define `<Picture 1>` as the frame or storyboard anchor and `<Subject 1>` as the primary person or object from that picture. Mention maintained environment coherence from `<Picture 1>` in `summary`, `retention_analysis`, and `detailed_description` without promoting the environment to another subject label, unless the picture is environment-only or the user explicitly assigns the environment as a subject.

For true single-image I2VA, use the exact first line `For the target video, at 0.00 seconds into the target video, <Picture 1> (from [Shot 1]) is fully referenced.` and follow it with one blank line. Do not use that opening for T2VA or ordinary Ref2Vid/full-reference inputs whose pictures define only bounded identity, subject, scene, style, or control roles.

In `retention_analysis`, list every actual shot in which each referenced subject or asset appears. If the result remains one materially continuous camera presentation and principal action, keep only `[Shot 1]` instead of manufacturing extra phase tags.

## Output Contract

Return:

1. A short `Reference map` when two or more references are used, when the user mentions a reference role for the request, or when subject and audio ownership would otherwise be easy to misread. Map `<Picture N>`, `<Video N>`, `<Audio N>`, and `<Subject N>` roles before the prompt.
2. One final prompt in a single plain-text code block, ready to paste.
3. A short `Assumptions` or `Watch-outs` note only when it helps execution.

For readability, format every field as a field label followed by line-broken content. Put each `subject_definitions` item, `retention_analysis` item, and tagged action phase on its own line. In `detailed_description` and base original outputs, put every `[Shot N]` tag on a new line under the field label. Keep `overall_soundscape:` and `non_diegetic_music:` as separate field labels with their own paragraphs.

Validate before returning:

- The output uses either base original fields or full-reference original fields, not a hybrid.
- Field names match the required structures exactly.
- References are labeled consistently and have bounded roles.
- The final prompt uses camera-visible and audible details instead of abstract meaning or inferred intent.
- The final prompt uses only reference tags that are attached, selected, or mentioned by the user for the same request.
- Single-image prompts use `<Picture 1>` and avoid extra `<Subject N>` labels for background context unless the image is environment-only, the user explicitly assigns the environment as a subject, or the environment has its own separate reference.
- Dialogue appears inside the relevant description field with `<d>[Language] ...</d>`.
- Dialogue uses `<d>` tags exactly and does not use bracketed quote style.
- Frame rate, aspect-ratio parameter text, and timestamp ranges are absent.
- The output keeps only `[Shot 1]` when camera presentation and principal action remain materially continuous, and adds a later shot only for a material camera or principal-action change.
- Keyframe alignment uses the supplied duration or the 5.00-second fallback, and every `[Shot N]` after `[Shot 1]` uses `At MM:SS.mmm` with a realistic phase-start time.
- A same-camera action change begins directly with the observable action. A material camera change names the cut, transition, framing, or movement and the new information it reveals.
- Phase-start times are strictly increasing and leave enough time for the visible action and dialogue that follow.
- Every later shot includes the concise Context Loop needed to preserve continuing identities, ownership, state, geography, environment, camera axis, and ambience.
- Every cut introduces new information, and every camera move states its visible result.
- Internal consent, age, safety, and policy checks are not exposed inside the final prompt.
- `overall_soundscape` contains ambience and physical sound only.
- `non_diegetic_music` is `N/A` when no audience-only music is requested.

Do not return competing variants unless requested.

---

# Full-Reference Mode Rewrite Output Format Guide

Organize and write full-reference rewrite outputs as follows.

Write all six rewrite sections in English. Preserve the original language only for dialogue and lyrics inside `<d>` and for text visibly present in the scene.

**Description detail:** Make `detailed_description` detailed, explicit, and chronological. In playback order, each actual shot establishes what the camera sees and microphone hears: visible composition, referenced subjects and current positions, environment and lighting, observable action and resulting state, relevant camera behavior, synchronized physical sound or dialogue, and the exact point where each reference takes effect. Avoid reducing the description to a plot summary or a list of reference relationships.

Use the same shot, camera-movement, speaker, dialogue, and ordinary-sound syntax as T2VA, I2VA, FL2VA, and L2VA. Apply the additional reference labels, analysis sections, and format differences below in full-reference mode.

## 1. Overall Structure

A complete rewrite output consists of six sections in the following order:

| Section | Purpose |
| --- | --- |
| `subject_definitions` | Defines referenced content and its reference labels |
| `summary` | Summarizes the task type, target video, and main reference relationships |
| `retention_analysis` | Describes how referenced content is preserved, transferred, or reused |
| `detailed_description` | Describes visuals, actions, shots, sound, and dialogue in playback order |
| `overall_soundscape` | Summarizes ambience and physical sounds |
| `non_diegetic_music` | Describes background music audible only to the audience |

## 2. Reference Labels and Definitions (`subject_definitions`)

Full-reference rewrites use four types of labels to identify the source and role of referenced content:

| Label | Meaning |
| --- | --- |
| `<Subject N>` | Visible content abstracted from reference assets that can be reused or modified in the target video |
| `<Picture N>` | A reference image used as a concrete target frame or shot-planning anchor |
| `<Video N>` | A reference video that provides an editing source, continuation starting point, or whole-video temporal structure |
| `<Audio N>` | An audio signal that is copied or referenced |

> Once a reference label is assigned to a piece of content, it keeps the same meaning across `subject_definitions`, `summary`, `retention_analysis`, `detailed_description`, and the audio sections.

Every label is a bounded authority. State both what it controls and what it must not contribute. A subject reference does not implicitly control pose, action, expression, framing, background, environment, lighting, camera, text, audio, surrounding people, or unrelated objects. A motion or camera reference does not contribute actors, identities, bodies, wardrobe, location, props, dialogue, sound, or visual style unless that role is explicitly assigned.

`subject_definitions` defines each piece of referenced content that must be tracked separately later, such as a person, an environment, a source video's structure, or an audio track. Give each item its own line and explain what its label denotes, its reference role, and the main features to follow; name the corresponding source asset when its origin must be explicit. If `<Picture N>` or `<Video N>` only identifies the source of another referenced item and will not be analyzed or used separately later, cite it inside that item's definition without adding a separate line. `retention_analysis` records where each referenced item appears and whether it is fully preserved, partially preserved, transferred, or reused.

### 2.1 `<Subject N>`

`<Subject N>` is used for reusable visible content, including:

- People, animals, or objects
- Scenes, backgrounds, or environments
- Clothing, props, interfaces, or visual effects
- Styles, actions, expressions, or poses

It represents a content unit that will actually be used in the target video, rather than the source file itself. One subject may be defined by multiple reference assets, and one reference asset may provide multiple subjects.

```text
<Subject 1> is the young woman in <Picture 1>, with long dark hair, a blue cardigan, and a thin silver necklace.
```

When the same subject comes from multiple assets, combine the sources and state what each asset provides:

```text
<Subject 1> is the woman whose appearance comes from <Picture 1> and whose walking motion comes from <Video 1>.
```

### 2.2 `<Picture N>`

Use a standalone `<Picture N>` when the reference image itself serves as a shot's first frame, keyframe, last frame, edited keyframe, or composition anchor:

```text
<Picture 2> is the first frame of [Shot 1], showing a woman seated beside a café window.
```

If an image is used only to define a character, scene, costume, or style, do not create a standalone picture entry. Instead, cite the image source inside the corresponding `<Subject N>` definition.

When an image acts as a storyboard or shot-planning reference, state which shots it maps to and what planning information it provides:

```text
<Picture 3> is a storyboard reference for [Shot 1] and [Shot 2], defining their viewpoint, subject placement, and shot order.
```

### 2.3 `<Video N>`

`<Video N>` is reserved for whole-video relationships, such as:

- Editing an original video
- Continuing from the end of an original video
- Referencing the original video's camera movement, cuts, rhythm, or temporal structure

```text
<Video 1> is the source video for the target video edit.
```

If a person, object, scene, action, or effect from a reference video is reused as visible content, it still belongs under `<Subject N>`. `<Video N>` identifies the asset or structural source and does not replace subject labels.

### 2.4 `<Audio N>`

`<Audio N>` represents a standalone audio asset or an enabled synchronized audio track from a reference video. Common uses include:

- Copying all or part of an audio signal
- Referencing a background-music style
- Referencing a speaker's voice timbre and delivery
- Using dialogue, lyrics, or sound effects from the original audio
- Referencing beat, rhythm, or audio continuity

When an `<Audio N>` explicitly corresponds to a target speaker, reuse that speaker's global ID in the definition: write `<Subject N> (Sx)` when the speaker maps to a defined subject, or use a stable voice description followed by `(Sx)` otherwise. The ID comes from the target video's global speaker order and is not independently assigned or renumbered in the audio definition. See Section 5.4 for the speaker-numbering rules:

```text
<Audio 1> is the voice-timbre reference for <Subject 1> (S1).
```

When one audio asset serves multiple roles, describe those roles in one natural sentence rather than creating additional subsections.

### 2.5 Visual and Audio Tracks from the Same Reference Video

`<Video N>` and `<Audio N>` are numbered independently. Each index indicates only the label's order within its own category and does not encode a pairing between the two categories. The same reference video may therefore correspond to `<Video 1>` and `<Audio 2>`; different indices do not prevent them from coming from the same source asset.

An ordinary reference video does not create `<Audio N>` merely because the file contains sound.

An `<Audio N>` definition primarily states the audio's role and does not have to name the `<Video N>` it comes from. State the shared source only when needed to remove ambiguity, for example:

```text
<Video 1> is the source video for the target video edit.
<Audio 2> is the synchronized audio track of <Video 1> and is reused in the target video.
```

## 3. `summary`

This section uses one short English paragraph to summarize the target video and its reference relationships. It begins with a square-bracketed task-type prefix:

```text
[reference generation] ...
[video editing + reference generation + audio reuse] ...
```

Choose task types from the actual role each reference asset plays in the target video:

| Task type | When to use it |
| --- | --- |
| `keyframe completion` | An image serves as the target video's first frame, keyframe, last frame, edited keyframe, or another concrete frame anchor |
| `reference generation` | An image, video, or audio asset provides generation guidance for a character, scene, style, action, camera movement, storyboard, and so on, without serving as a concrete frame or as the source video being edited or continued |
| `video editing` | An existing source video is directly modified; editing an image or generating between still keyframes does not belong to this type |
| `video continuation` | New content continues, extends, resumes, or transitions from an existing source video |
| `audio reuse` | The same audio signal is reused in full or in part |
| `audio reference` | The audio signal is not copied directly; only its music style, timbre, dialogue or lyric content, sound-effect texture, beat, or continuity is referenced |

When a task satisfies multiple relationships, combine the task types with ` + ` and do not repeat a type. For example, continuing from a source video while using an image as the last frame is written as `[video continuation + keyframe completion]`. Editing a source video while retaining its original audio may be written as `[video editing + audio reuse]`.

The mere presence of video or audio does not automatically create a corresponding task type. If a reference video provides only camera movement, cuts, or rhythm, it normally belongs to `reference generation`. Use `video editing` or `video continuation` only when that video is directly edited or continued.

When editing a source video, use `audio reuse` as well if its original audio remains audible. When continuing a source video without directly copying the audio signal, use `audio reference` if the new audio only continues the original track's audible characteristics.

The summary uses the previously defined `<Subject N>`, `<Picture N>`, `<Video N>`, and `<Audio N>` labels to describe the main subjects, actual shot flow, and roles of the reference assets. Do not introduce new reference labels in this section. Do not describe manufactured phase segmentation: keep one shot when camera presentation and principal action remain materially continuous, and summarize later shots only when a material camera or principal-action change actually requires them.

For video-editing tasks, begin the summary after the task-type prefix with:

```text
The target video is an edited version of <Video 1>.
```

## 4. `retention_analysis`

This section describes how each piece of referenced content is preserved, transferred, copied, or referenced in the target video. Use one line for each reference label and preserve the meaning established in `subject_definitions`. List every actual shot in which the referenced content appears. Do not create extra shots merely to repeat a continuing subject; when camera presentation and principal action remain materially continuous, the content appears in `[Shot 1]` only.

### 4.1 Visible Content

`<Subject N>`, `<Picture N>`, and `<Video N>` use the following relationship markers. These markers are fixed English values in the output format:

| Relationship marker | Meaning |
| --- | --- |
| `fully_preserved` | The defined role of the referenced content is fully preserved |
| `partially_preserved` | The referenced content is still used, but some defined characteristics are changed or only partially retained |
| `attribute_transfer` | Referenced characteristics are transferred to a different identifiable target subject |
| `weak_reference` | Only broad similarity in style, category, composition, or atmosphere is retained |

Subject entry:

```text
<Subject 1> (appears in [Shot 1], [Shot 3]): fully_preserved - ...
```

Picture entry:

```text
<Picture 2> ([Shot 1] first frame): fully_preserved - ...
```

Video-structure entry:

```text
<Video 1> (cut and pacing structure): weak_reference - ...
```

### 4.2 Audio

`<Audio N>` uses the following relationship markers:

| Relationship marker | Meaning |
| --- | --- |
| `fully_copy` | The complete source audio serves as the target video's complete final audio track |
| `partially_copy` | Only part of the timeline or selected audio layers are copied, or other sounds are added, removed, or replaced after copying |
| `reference` | The signal is not copied directly; only timbre, rhythm, music style, dialogue content, or sound texture is referenced |
| `weak_reference` | Only broad similarity in category or atmosphere is retained |

```text
<Audio 1>: fully_copy - <Audio 1> is reused 1:1 as the target video's complete final audio track.
```

```text
<Audio 2>: reference - the target speaker follows <Audio 2>'s voice timbre, identity parameters and mannerism and measured delivery without copying the original signal.
```

Choose each relationship marker only within the reference role already defined for that label in `subject_definitions`. Do not treat newly added actions, backgrounds, or plot events in the target video as losses of reference fidelity.

## 5. `detailed_description`

This is the main body of a full-reference rewrite. It describes visuals, actions, sound, and dialogue shot by shot in target-video playback order and inserts reference labels where they apply.

### 5.1 Basic Format

The basic format follows the Video Prompt Writing Guide (T2VA / I2VA / FL2VA / L2VA):

- Write the body in English. Preserve the original language of dialogue, lyrics, and visible text.
- `[Shot 1]` marks the opening and has no timestamp. Keep only `[Shot 1]` while the camera presentation and principal action remain materially continuous. Add a later shot only when the camera materially changes or the principal action changes to a distinct observable beat.
- Every later shot uses `[Shot N] At MM:SS.mmm, ...` with a realistic, strictly increasing phase-start time inside the supplied duration or a 5.00-second fallback when duration is absent.
- For a same-camera action change, begin directly with the observable action and do not add continuity boilerplate. For a material camera, viewpoint, location, time, or edit change, name the cut, transition, new framing, or movement and the new information it reveals.
- Apply a concise Context Loop at every later shot, re-anchoring only the continuing identities/count, wardrobe and prop ownership, body/object/contact state, screen geography, environment/lighting, camera framing/axis, and audible ambience needed to prevent drift.
- Write camera movement as natural English within the current shot, including movement type, amplitude, and speed when they need to be expressed.
- Give vocal sources stable `(S1)`, `(S2)`, and subsequent IDs. Write dialogue and lyrics as `<d>[Language] ...</d>`.
- Use `<scenetrans>`, `<cutoff>`, and the corresponding continuity descriptions for dialogue crossing a cut, speech truncated by the video ending, and continuous audio across shots.

For complete rules and examples covering camera vocabulary, group speech, voice-over, dialogue across cuts, and visible text, see the Video Prompt Writing Guide (T2VA / I2VA / FL2VA / L2VA).

### 5.2 Full-Reference Mode Differences

| Dimension | T2VA | Full-reference mode |
| --- | --- | --- |
| Main field | `integrated_multimodal_description` | `detailed_description` |
| Style opening | Written after `[Shot 1]` | Established in one or two English sentences before `[Shot 1]` |
| Reference information | Does not use full-reference labels | Inserts `<Subject N>`, `<Picture N>`, `<Video N>`, and `<Audio N>` at their first appearance and where their roles apply |
| Audio relationships | Describes the target video's own sound | Cites `<Audio N>` in the corresponding shot or audio phase and states whether the signal is copied or referenced |

Opening example:

```text
The target video is in a cinematic, literary music-video style with soft lighting and a slightly desaturated color palette.
[Shot 1] The scene opens in a crowded urban street...
[Shot 2] At 00:04.000, the continuing subject begins a distinct next action while identity, wardrobe, screen position, street lighting, camera framing, and traffic ambience remain coherent...
[Shot 3] At 00:09.000, the shot cuts to an extreme close-up...
```

For generation tasks, make `detailed_description` complete enough to cover the visible and audible timeline. Dialogue-dense content prioritizes fitting the complete spoken timeline. Video-editing descriptions scale with the complexity of the input video. One continuous camera take still requires adequate detail across its sequentially tagged action phases and across genuine cuts based on continuity and information load.

### 5.3 Using Reference Labels in Shots

At the first clear appearance of an important `<Subject N>`, describe its referenced characteristics, position in the frame, and current action within what is actually visible in the shot. Continue using the same label in later shots without redefining what the label represents.

Use natural phrasing for concrete frame anchors:

```text
the shot begins from <Picture 1>
the shot's keyframe corresponds to <Picture 2>
the shot ends on <Picture 3>
```

When editing or continuing an original video, cite `<Video N>` naturally where its source state, structure, or continuation relationship applies. Cite `<Audio N>` in the shot or semantic phase where the audio relationship is active.

