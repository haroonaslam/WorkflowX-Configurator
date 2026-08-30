# MiniMax H3 Official T2VA / Text to Video

## Generation type

- **T2VA**: Builds a complete audiovisual timeline from text.

For T2VA, select the overall style and initial composition from the user's text.

**T2VA** has no image-alignment instruction and begins directly with the three core fields.

### Part Two Contains the Three Core Fields

```text
integrated_multimodal_description: [Shot 1] ...

overall_soundscape: ...

non_diegetic_music: ...
```

- **integrated_multimodal_description**: Describes visuals, actions, shots, speakers, dialogue, singing, and diegetic audio along the timeline.
- **overall_soundscape**: Summarizes ambient sound, physical action sounds, and non-verbal human sounds across the entire video.
- **non_diegetic_music**: Describes background music that the characters cannot hear and only the audience can hear.

### Case: T2VA

With no reference image, construct the complete timeline directly from the text. You may add scene, character, action, and sound details that remain consistent with the user's intent.

```text
integrated_multimodal_description:
[Shot 1] Live-action, cinematic, a medium-wide shot frames a baker opening the shutters of a small street bakery before sunrise. The camera pushes in with small amplitude at slow speed as the middle-aged baker with a calm, slightly raspy voice (S1) places a fresh loaf on the wooden counter and says: <d>[English] First batch of the morning.</d>
[Shot 2] At 00:05.000, the camera cuts to a close-up of steam rising from the sliced bread while the baker's final words carry over from the previous shot.

overall_soundscape: Wooden shutters scrape open over a quiet street as trays clink softly inside the bakery. The doorbell rings once, followed by light footsteps and the crisp sound of bread being sliced.

non_diegetic_music: A soft acoustic-guitar pattern at a moderate tempo, joined by sparse upright-bass notes and a gentle fade at the end.
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
