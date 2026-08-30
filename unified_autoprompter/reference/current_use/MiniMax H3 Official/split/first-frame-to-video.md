# MiniMax H3 Official I2VA / First Frame to Video

When a model-facing choice depends on the supplied image, choose one definitive value that best fits the brief and reference.

## Generation type

- **I2VA**: T2VA body + first-frame instruction + a visual path that develops forward from the first frame.

For keyframe tasks, derive the overall style and initial composition from the reference image.

**I2VA** always uses:

```text
For the target video, at 0.00 seconds into the target video, <Picture 1> (from [Shot 1]) is fully referenced.
```

The instruction must be the first line of the final prompt, followed by one blank line before the core fields.

### Part Two Contains the Three Core Fields

```text
integrated_multimodal_description: [Shot 1] ...

overall_soundscape: ...

non_diegetic_music: ...
```

- **integrated_multimodal_description**: Describes visuals, actions, shots, speakers, dialogue, singing, and diegetic audio along the timeline.
- **overall_soundscape**: Summarizes ambient sound, physical action sounds, and non-verbal human sounds across the entire video.
- **non_diegetic_music**: Describes background music that the characters cannot hear and only the audience can hear.

### I2VA: Begin from the Image and Develop Forward

`<Picture 1>` is the actual first frame of the video at 0.00 seconds and belongs to `[Shot 1]`. The description should first establish the style, subjects, composition, and scene anchors in the image, then describe the next action. Character identity, clothing, colors, key objects, and spatial relationships should remain consistent.

Recommended structure: **first-frame anchor → action onset → continuous development → result or reaction**.

### Case: I2VA

Write the first-frame instruction first, then use the subject, composition, and scene in Picture 1 as the starting point of Shot 1 before describing how the scene continues to develop.

```text
For the target video, at 0.00 seconds into the target video, <Picture 1> (from [Shot 1]) is fully referenced.

integrated_multimodal_description:
[Shot 1] Live-action, cinematic, the young woman shown in <Picture 1> remains beside the rain-covered train window, preserving her appearance, clothing, seat position, and the carriage layout. The camera trucks right with small amplitude at slow speed as she lifts her gaze from the folded letter toward the passing city lights. Her reflection moves across the glass while the quiet, breathy young woman (S1) says: <d>[English] I get off at the next station.</d> She folds the letter along its existing crease while remaining in the same framing.

overall_soundscape: The train wheels produce a steady metallic rhythm beneath a low ventilation hum. Rain ticks against the window while paper rustles softly in her hands.

non_diegetic_music: Sustained cello notes at a slow tempo with widely spaced piano tones, gradually decreasing in volume.
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
