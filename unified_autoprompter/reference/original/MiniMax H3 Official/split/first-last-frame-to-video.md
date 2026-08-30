# MiniMax H3 Official FL2VA / First–Last Frame to Video

When a model-facing choice depends on the supplied images, choose one definitive value that best fits the brief and references. Use the requested duration for the keyframe-alignment instruction. If no duration is supplied, use the 5.00-second fallback for the keyframe-alignment line.

## Generation type

- **FL2VA**: T2VA body + first-and-last-frame instruction + a continuous path from the first frame to the last frame.

For keyframe tasks, derive the overall style and initial composition from the reference image.

**FL2VA** always uses:

```text
How the reference pictures align with the target video — Picture 1 (from Shot 1) aligns with the 0.00-second mark of the target video; Picture 2 (from Shot N) aligns with the S.SS-second mark of the target video.
```

The instruction must be the first line of the final prompt, followed by one blank line before the core fields.

For FL2VA, use the requested duration, or the 5.00-second fallback when absent, as the final alignment time formatted to exactly two decimals in the required first line. Prefer one `[Shot 1]` when the camera presentation and principal action remain materially continuous. Add timed later shots only for material camera or principal-action changes, and make the final shot arrive at the aligned last-frame state.

### Part Two Contains the Three Core Fields

```text
integrated_multimodal_description: [Shot 1] ...

overall_soundscape: ...

non_diegetic_music: ...
```

- **integrated_multimodal_description**: Describes visuals, actions, shots, speakers, dialogue, singing, and diegetic audio along the timeline.
- **overall_soundscape**: Summarizes ambient sound, physical action sounds, and non-verbal human sounds across the entire video.
- **non_diegetic_music**: Describes background music that the characters cannot hear and only the audience can hear.

### FL2VA: Describe the Path Between the First and Last Frames

Picture 1 is the opening, and Picture 2 is the ending. Focus on how the subject moves, how poses change, how objects are manipulated, how the composition evolves, and how the scene or lighting transitions.

FL2VA generally favors one continuous camera presentation so the model can interpolate continuously from the first frame to the last frame. Keep the whole bridge in `[Shot 1]` when the camera presentation and principal action remain materially continuous. Add a timed later shot only when the camera materially changes or the principal action changes to a distinct observable beat. The last frame must be reached by the final `[Shot N]` at the end of the video.

Recommended structure: **first-frame state → observable intermediate changes → progressively narrowing differences → last-frame state**.

### Case: FL2VA

The two images anchor the opening and ending respectively. The body should not repeat two static image descriptions; instead, it should supply the motion path that connects them. The following example uses timed later shots because the principal action changes materially several times during the eight-second bridge.

```text
How the reference pictures align with the target video — Picture 1 (from Shot 1) aligns with the 0.00-second mark of the target video; Picture 2 (from Shot 4) aligns with the 8.00-second mark of the target video.

integrated_multimodal_description:
[Shot 1] Live-action, cinematic, a rain-soaked cyclist begins in the position and framing established by Picture 1, holding a closed black umbrella beside a silver bicycle. The camera pulls out with small amplitude at slow speed as she releases the bicycle handle and raises the umbrella above her shoulder.
[Shot 2] At 00:02.000, the same cyclist presses the runner upward until the canopy opens and water rolls from the expanding fabric; her silver bicycle remains beside her in the rain-soaked street under the same framing and ambience.
[Shot 3] At 00:05.000, the cyclist steps beneath the umbrella and rotates the handle into the final angle, preserving her appearance, bicycle position, camera axis, wet pavement, and steady rainfall.
[Shot 4] At 00:07.000, she settles into the pose, spacing, and composition established by Picture 2 while the same camera framing, street lighting, bicycle ownership, and rain ambience remain coherent through the final frame.

overall_soundscape: Rain falls steadily on the pavement, followed by the metallic click of the umbrella runner and the soft snap of the canopy opening. Water drips from the bicycle frame as distant traffic passes.

non_diegetic_music: N/A
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
