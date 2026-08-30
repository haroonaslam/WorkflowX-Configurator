# MiniMax H3 Official Common Rules and Guide

Create copy-ready MiniMax H3 prompts using the required output structures and field syntax.

## Prompt-Output Hygiene

- Do not include multiple-choice or fallback phrasing in the final prompt. Avoid "or", slashes, "acceptable", "either", "if possible", and option pairs such as "vertical or square" or "Urdu / Roman Urdu." When the user leaves a model-facing choice unclear, choose one definitive value that best fits the brief.

- Be explicit. Do not rely on the model to infer who acts, who speaks, what happens between beats, or what must stay unchanged. Write what the camera sees and the microphone hears, not what the scene means. Use concrete observable details: framing, screen geography, subject, wardrobe, prop, setting, action, resulting state, camera, lighting, ambience, synchronized physical sound, dialogue, and audible tails.

- Keep frame rate and aspect ratio out of the final prompt because those are generation parameters. Use the user's requested duration for realistic later-shot phase-start times. If no duration is supplied, assume a 5.00-second target timeline for pacing and timestamps. Do not state that assumed duration as general prose. Do not write "24 FPS", "9:16", "vertical aspect ratio", timestamp ranges, or similar parameter language into the prompt.

- Before writing the final prompt, determine whether the camera presentation or principal action materially changes. A principal-action change starts a distinct observable beat: the action changes target, prop, contact state, body state, active performer, dialogue phase, reaction, or final pose. Do not split subordinate movements that merely complete one uninterrupted principal action.

- Use `[Shot 1]` for the opening and keep only `[Shot 1]` when both the camera presentation and principal action remain materially continuous. Add the next sequential `[Shot N]` only when the camera materially changes or the principal action materially changes. `[Shot 1]` has no timestamp. Every later shot begins on its own line with `[Shot N] At MM:SS.mmm, ...`, using a realistic, strictly increasing phase-start time inside the supplied or assumed duration.

- When only the action changes and the camera does not, begin the later shot directly with the observable action. Do not write "without a cut", "the same continuous camera take continues", or equivalent continuity boilerplate. When the camera, viewpoint, location, time, or edit materially changes, name the exact cut, transition, new framing, or camera movement and the new information it reveals.

- At every later shot, apply a concise Context Loop: re-anchor only the continuing subject identity and count, wardrobe and prop ownership, current body/object/contact state, screen position and direction, environment and lighting, camera framing and axis, and audible ambience needed to prevent drift.

- 
  Before writing timed phases, estimate whether the requested action, dialogue, and final state fit naturally. If the scene is too dense, compress low-priority transitions first, cut directly to a later observable state when justified, use a motivated cut when continuity cannot carry the next phase, or mention the timing risk outside the prompt instead of forcing physically impossible action.

- Do not overload short clips with too many actions, locations, camera moves, subjects, or dialogue turns. Give each material phase one primary visible event and a usable resulting state. A cut must introduce new information: subject, state, viewpoint, space, or time. If only distance or a slight angle changes, prefer camera motion within the current shot. Pair each camera movement with the visible result it creates, such as the newly revealed subject, changed composition, or clearer action detail.


## Dialogue Rules

Original MiniMax format uses `<d>` tags. Place spoken lines naturally inside `integrated_multimodal_description` or `detailed_description`, not in a standalone dialogue section.

Use this format:

```text
<Subject 1> (S1) says in a <delivery> voice: <d>[English] Hello, how are you?</d>
<Subject 1> (S1) says in a <delivery> voice: <d>[Urdu] <native-script Urdu line></d>
```

Use `<d>[Language] spoken text</d>` exactly for MiniMax original dialogue. Do not use the H3 prompt style `[Language] "spoken text"` in this format. Do not put quotation marks inside `<d>`. Do not add a standalone `[DIALOGUE]` field. Put the speaker label, delivery, and action outside `<d>`, and put only the language tag plus spoken content inside `<d>`.

When the user asks for a specific spoken language, write the final dialogue in that language's native script when the language normally uses one. If the user provides romanized Urdu or Hindi, convert it to native script unless they explicitly ask to keep romanized text. Preserve exact user-provided wording when the user supplies native-script dialogue.

Assign `(S1)`, `(S2)`, and later speaker IDs in the order of actual vocal events. Reuse the same speaker ID across shots. Do not repeat dialogue in `overall_soundscape` or `non_diegetic_music`.

## Shared shot, camera, dialogue, on-screen text, and audio guide

### Shots, Timed Action Beats, and Cuts

Before writing, determine whether the camera presentation or principal action materially changes. A principal-action change starts a distinct observable beat: the action changes target, prop, contact state, body state, active performer, dialogue phase, reaction, or final pose. Keep subordinate movements that complete one uninterrupted principal action in the same shot.

Begin with `[Shot 1]` and do not timestamp it. Keep only `[Shot 1]` while both camera presentation and principal action remain materially continuous. Add `[Shot 2]`, `[Shot 3]`, and later tags only when the camera materially changes or the principal action materially changes. Every later tag uses `[Shot N] At MM:SS.mmm, ...` with a realistic, strictly increasing phase-start time inside the supplied duration. If no duration is supplied, assume a 5.00-second target timeline for pacing and timestamps without writing that assumption as general prose.

For a same-camera action change, begin directly with the observable action and resulting state:

```text
[Shot 1] Live-action, a medium shot establishes the subject performing the opening action.
[Shot 2] At 00:02.000, the same subject begins the distinct next action, preserving wardrobe, prop ownership, screen position, lighting, framing, and room ambience; the action ends with a clear visible result.
```

Do not add `without a cut`, `the same continuous camera take continues`, or equivalent continuity boilerplate. The unchanged camera and the Context Loop already preserve continuity.

When the camera, viewpoint, location, time, or edit materially changes, name the transition and the new information it reveals:

```text
[Shot 2] At 00:03.500, the camera cuts to a close-up that reveals...
```

For ordinary cuts, use `the camera cuts to`, `the shot cuts to`, `the shot transitions to`, `the shot changes to`, or `the shot switches to`. When explicitly requested by the user, cross-dissolve, fade, or wipe may also be used. A cut must introduce new information about the subject, space, state, viewpoint, or time. If only distance or a slight angle changes, prefer a motivated camera movement and state its visible result.

At each later shot, apply a concise Context Loop: re-anchor only the continuing subject identity/count, wardrobe and prop ownership, current body/object/contact state, screen position/direction, environment/lighting, camera framing/axis, and audible ambience needed to prevent drift. Do not use timestamp ranges.

### Camera Motion: Motion Type + Amplitude + Speed

A complete camera-motion expression has three dimensions: the **motion type** defines how the camera moves, **amplitude** defines the range of compositional change, and **speed** defines the pacing of that change. Add amplitude and speed only when they are meaningful; medium amplitude and normal speed are usually omitted.

| Dimension | Available Expression | Description |
|-|-|-|
| Motion type | `Zoom In / Zoom Out` | The focal length changes while the camera body remains stationary |
| Motion type | `Push In / Pull Out` | The camera moves forward / backward |
| Motion type | `Pan Left / Pan Right` | The camera remains in place while the lens pivots horizontally |
| Motion type | `Truck Left / Truck Right` | The camera translates horizontally |
| Motion type | `Tilt Up / Tilt Down` | The camera remains in place while the lens pivots vertically |
| Motion type | `Pedestal Up / Pedestal Down` | The entire camera moves upward / downward |
| Motion type | `Arc Shot` | The camera moves in an arc around the subject |
| Motion type | `Tracking Shot` | The camera follows a moving subject |
| Motion type | `Static Shot` | The camera position and lens remain still |
| Motion type | `Shake Slightly / Shake Strongly` | Slight / strong camera shake |
| Motion type | `POV` | The subject's point of view |
| Motion type | `Roll Clockwise / Roll Counterclockwise` | The camera rolls clockwise / counterclockwise around the lens axis |
| Amplitude | `with small amplitude` | Small-range change |
| Amplitude | `with large amplitude` | Large-range change |
| Speed | `at slow speed` | Slow movement |
| Speed | `at fast speed` | Fast movement |

Camera motion should be written as a natural English action within the shot, rather than stacked as separate labels at the end of a sentence:

```text
The camera pushes in with small amplitude at slow speed toward the folded letter in her hands.
The camera pans right with large amplitude at fast speed, revealing the open doorway.
The camera holds a static shot as the runner exits the frame.
```

### Speakers, Dialogue, and Singing

Subjects who speak, sing, or produce an off-screen human voice use stable IDs such as `(S1)` and `(S2)`. When multiple already-numbered speakers speak or sing together, use a compound ID such as `(S1,S2)`. A speaker keeps the same ID across shots; characters who never vocalize receive no speaker ID.

When a speaker first appears, provide enough information from the visual and audio context to establish a stable identity, such as character type, age, gender, whether the person is on-screen, pitch, timbre, speaking rate, or accent. Place the speaker's identifying phrase, ID, action, and delivery outside `<d>`. Inside `<d>`, include only the language tag and the actual user-provided spoken content. Preserve every original word and punctuation mark verbatim; do not translate or rewrite them.

```text
The young woman with a quiet, breathy voice (S1) says: <d>[English] I get off at the next station.</d>
The two children (S1,S2) shout together, <d>[English] Wait for us!</d>
```

For voiceover, use the exact phrase `says in an off-screen voiceover`. Immediately after every voiceover `<d>` block, state that the corresponding on-screen character's lips remain closed:

```text
The man (S1) says in an off-screen voiceover: <d>[English] I still remember that road.</d> while his lips remain completely closed.
```

When the same line of dialogue or lyrics crosses a cut, use `<scenetrans>` at the connecting points in both parts and explicitly state that the audio continues across the cut. Use `<cutoff>` when speech is truncated by the end of the video. Continuity may be expressed with `continues seamlessly across the cut`, `continues uninterrupted into the next shot`, `carries over from the previous shot`, or `remains audible across the transition`.

### On-Screen Text

Place any banner, sign, label, subtitle, or neon text that is actually visible on screen in English double quotation marks. Preserve the original text and punctuation verbatim, without translation.

```text
A red neon sign reading "营业中" glows above the doorway.
```

### overall_soundscape

Use 1–4 English sentences in one continuous paragraph to summarize the ambient sound, physical action sounds, and non-verbal human sounds across the full video, such as wind, rain, traffic, footsteps, fabric movement, impacts, breathing, laughter, or panting. Dialogue, singing, and diegetic music already belong in the multimodal description and should not be repeated here. Use `N/A` only when the user explicitly requests complete silence throughout the video.

```text
overall_soundscape: Steady rain taps against the café windows while low room ambience continues underneath. The entrance bell rings once, followed by wet footsteps and the soft scrape of a chair.
```

### non_diegetic_music

Use 1–3 English sentences to describe background music that the characters cannot hear and only the audience can hear. Focus on instrumentation, speed, rhythm, and dynamic changes; do not use abstract mood words or explain the emotional function of the score. Singing, instruments, radio, television, or phone music audible to the characters are diegetic events and should appear in the multimodal description. Use `N/A` when there is no non-diegetic music.

```text
non_diegetic_music: Sparse piano notes at a slow tempo, joined by sustained low strings that gradually increase in volume before fading out.
```

## Initial style and composition

At the beginning of `[Shot 1]`, state the overall style and initial composition. Common styles include `Cinematic`, `Amateur`, `Private video`, `Influencer Social Media`, `live-action`, `2D-animated`, `3D CG`, `claymation`, `watercolor`, and `vintage film`. For keyframe tasks, derive the style from the reference image; for T2VA, select it from the user's text.
