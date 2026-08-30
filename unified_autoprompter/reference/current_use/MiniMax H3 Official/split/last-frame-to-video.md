# MiniMax H3 Official L2VA / Last Frame to Video

When a model-facing choice depends on the supplied image, choose one definitive value that best fits the brief and reference. Use the requested duration for the keyframe-alignment instruction. If no duration is supplied, use the 5.00-second fallback for the keyframe-alignment line.

## Generation type

- **L2VA**: T2VA body + last-frame instruction + a path that converges from a plausible preceding state to the last frame.

For keyframe tasks, derive the overall style and initial composition from the reference image.

**L2VA** always uses:

```text
How the reference pictures align with the target video — <Picture 1> (from [Shot N]) aligns with the S.SS-second mark of the target video.
```

Here, `N` is the index of the actual final shot, and `S.SS` is the effective video duration formatted to exactly two decimal places. The instruction must be the first line of the final prompt, followed by one blank line before the core fields.

For L2VA, use the requested duration, or the 5.00-second fallback when absent, as the final alignment time formatted to exactly two decimals in the required first line. Prefer one `[Shot 1]` when the camera presentation and principal action remain materially continuous. Add timed later shots only for material camera or principal-action changes, and make the final shot arrive at the aligned last-frame state.

### Part Two Contains the Three Core Fields

```text
integrated_multimodal_description: [Shot 1] ...

overall_soundscape: ...

non_diegetic_music: ...
```

- **integrated_multimodal_description**: Describes visuals, actions, shots, speakers, dialogue, singing, and diegetic audio along the timeline.
- **overall_soundscape**: Summarizes ambient sound, physical action sounds, and non-verbal human sounds across the entire video.
- **non_diegetic_music**: Describes background music that the characters cannot hear and only the audience can hear.

### L2VA: Infer the Opening and Land on the Image at the End

`<Picture 1>` is the final frame of the video and belongs to the last `[Shot N]`; it does not inherently belong to Shot 1. Infer a plausible earlier state from the user's intent and the last frame, then describe how the characters, objects, camera, and scene gradually approach the reference image.

Recommended structure: **plausible preceding state → explicit action and transition path → gradual convergence in the final shot → last-frame landing**.

### Case: L2VA

The image anchors only the final moment. First establish a compatible earlier state, then let the actions, object states, and composition gradually land on Picture 1 in the final tagged phase. The following example uses timed later shots because the principal action changes materially several times during the six-second approach.

```text
How the reference pictures align with the target video — <Picture 1> (from [Shot 4]) aligns with the 6.00-second mark of the target video.

integrated_multimodal_description:
[Shot 1] Live-action, cinematic, a close shot begins with an intact drinking glass near the edge of a dark wooden table, while the same hand and sleeve visible in <Picture 1> approach from the right. The camera pushes in with small amplitude at slow speed.
[Shot 2] At 00:01.500, the same hand strikes the rim and the glass begins to tip, preserving the dark wooden table, sleeve, camera angle, lighting, and quiet room tone.
[Shot 3] At 00:03.000, the glass falls and hits the floor with a sharp impact; cracks spread through it as fragments slide outward while the same hand, room, lighting, framing, and camera axis remain coherent.
[Shot 4] At 00:05.000, the moving pieces lose momentum and settle into the exact broken arrangement, hand position, camera angle, lighting, and final composition established by <Picture 1>; small fragments audibly finish sliding across the floor.

overall_soundscape: Fingertips tap the glass before it scrapes across the tabletop, falls, and breaks with a sharp crash. Small fragments scatter and gradually stop sliding across the floor.

non_diegetic_music: A low electronic pulse at a slow tempo, ending immediately after the glass breaks.
```

## Three-field generation guide

At the beginning of `[Shot 1]`, state the overall style and initial composition. Common styles include `Cinematic`, `Amateur`, `Private video`, `Influencer Social Media`, `live-action`, `2D-animated`, `3D CG`, `claymation`, `watercolor`, and `vintage film`.

## How to Write the Three Shared Core Sections

### Develop the Multimodal Description Along the Timeline

`integrated_multimodal_description` is the main body of the rewritten prompt. Every detail should correspond to something visible or audible: visual style, initial composition, subject appearance and position, scene and key props, actions and reactions, shot changes, spoken language, and synchronized diegetic sound.

```text
[Shot 1] Live-action, cinematic, a medium-wide shot frames...
```

Use only `[Shot 1]` while the camera presentation and principal action remain materially continuous. Add a timed later `[Shot N]` only for a material camera or principal-action change, as defined in Section 4.2.
