# MiniMax H3 Alternate Common Rules and Guide

## Task selection

Choose the smallest contract that fits:

Infer harmless production details when the user's intent is clear. Ask only when a missing answer would change exact dialogue or story outcome.

## Prompt-output hygiene

- Do not include multiple-choice or fallback phrasing in the final prompt. Avoid "or", slashes, "acceptable", "either", "if possible", and option pairs such as "vertical or square" or "Urdu / Roman Urdu." When the user leaves a model-facing choice unclear, choose one definitive value that best fits the brief. For personal/private phone-video briefs, use handheld phone framing. For general cinematic or landscape briefs, use the camera feel and composition implied by the brief. 

- Be explicit. Do not rely on the model to infer who acts, who speaks, what happens between beats, or what must stay unchanged. Write what the camera sees and the microphone hears, not what the scene means. Use concrete observable details: framing, screen geography, subject, wardrobe, prop, setting, action, resulting state, camera, lighting, ambience, synchronized physical sound, dialogue, and audible tails.

- Keep frame rate and aspect ratio out of the final prompt because those are generation parameters. Use the user's requested duration to create realistic later-shot phase-start times. If no duration is supplied, assume a 5.00-second target timeline for pacing and timestamps without stating that assumption as general prose. Do not write "5 seconds", "9:16", "vertical aspect ratio", timestamp ranges, or similar parameter language as general prose unless the user explicitly asks for that text as visible/story content. Describe camera feel instead, such as handheld phone framing, close selfie distance, counter-height angle, locked-off tripod, or over-the-shoulder view.

- Use native dialogue tags for exact spoken lines:

  ```text
  [English] "Hello, how are you?"
  [Urdu] "<native-script Urdu line>"
  ```

- When the user asks for a specific spoken language, write the final dialogue in that language's native script when the language normally uses one. If the user provides romanized Urdu or Hindi, convert it to the native script in the final prompt unless they explicitly ask to keep romanized text on screen. Bind delivery separately in prose, but keep the spoken line in the bracketed language format.


## Stable truth

Lock subject count, face, hair, body, wardrobe, prop ownership, voice ownership, left/right relationships, look room, and screen direction only when they matter to continuity.

Give actors an objective and listening behavior. Prefer observable direction-breath, gaze, posture, interrupted movement, hesitation, or attention-over generic emotion labels.

## Stage shots and timed action beats

Before writing the final prompt, determine whether the camera presentation or principal action materially changes and assign each actual beat enough time for movement, dialogue, reaction, and an audible tail. A principal-action change starts a distinct observable beat: the action changes target, prop, contact state, body state, active performer, dialogue phase, reaction, or final pose. Keep subordinate movements that complete one uninterrupted principal action in the same shot.

Begin with `[SHOT 1]` and do not timestamp it. Keep only `[SHOT 1]` while camera presentation and principal action remain materially continuous. Add `[SHOT 2]`, `[SHOT 3]`, and later tags only when the camera materially changes or the principal action materially changes. Every later shot uses `[SHOT N] At MM:SS.mmm, ...` with a realistic, strictly increasing phase-start time inside the supplied duration or a 5.00-second fallback when duration is absent.

For a same-camera action change, begin directly with the action and its visible result:

```text
[SHOT 1] <framing and lens>; <camera behavior>; <opening visible action and state>.
[SHOT 2] At 00:02.000, <the continuing subject begins the distinct next action>; preserve the needed identity, wardrobe, prop ownership, screen geography, lighting, framing, ambience, and <visible result>.
```

Do not write `without a cut`, `the same continuous camera take continues`, or equivalent boilerplate. When the camera, viewpoint, location, time, or edit materially changes, name the exact cut, transition, new framing, or camera movement and the new information it reveals:

```text
[SHOT 2] At 00:03.500, the camera cuts to <new framing, newly revealed information, action, dialogue, and visible end state>.
```

At every later shot, apply a concise Context Loop: re-anchor only the continuing subject identity/count, wardrobe and prop ownership, current body/object/contact state, screen position/direction, environment/lighting, camera framing/axis, and audible ambience needed to prevent drift.

- Do not use timestamp ranges such as `0-1.2s`. Treat phase-start times and cut times as pacing guidance, not frame-accurate edit commands.
- Give each actual shot one primary visible event and a usable resulting state.
- Do not overload short clips with too many actions, locations, camera moves, subjects, or dialogue turns. Compress low-priority transitions first; use a motivated cut only when continuous staging cannot carry the next phase clearly or naturally.
- A cut must introduce new information: subject, state, viewpoint, space, or time. If only distance or a slight angle changes, prefer camera motion within the current shot.
- Pair each camera movement with the visible result it creates, such as the newly revealed subject, changed composition, or clearer action detail.
- Reserve time for reactions and audible scene tails. Keep screen geography and eyelines consistent across continuous phases and across cuts.
- Use only `[SHOT 1]` when camera presentation and principal action remain materially continuous. Add a timed later shot when either materially changes.
- If the requested action, dialogue, and final state cannot fit naturally, compress low-priority transitions, cut directly to a later observable state when justified, or note the timing risk outside the prompt instead of forcing physically impossible action.
- Do not create a standalone `[DIALOGUE]` section. Place each spoken line inside the shot and timed phase where it should happen. Multiple lines of dialogue should appear in chronological order.

## Separate finishing direction

After the shot list, use only the sections that constrain the result:

```text
[ACTING]
[LIGHT AND IMAGE]
[CAMERA]
[PRODUCTION SOUND]
[NEGATIVES]
```

State dialogue as exact bracketed-language lines inside the applicable shot, such as `[Urdu] "<native-script line>"`. Name accent, delivery, and timing in prose outside the quoted spoken line. Keep dialogue separate from the final audio mix.

Keep negatives short and specific to likely failures: extra subjects, identity drift, wardrobe swaps, voice swaps, broken eyelines, duplicate props, incorrect screen direction, unmotivated cuts, subtitles, or unwanted music.

Do not use negatives for internal safety logic. Exclude age, consent, policy, legality, user attestation, and moderation language from `[NEGATIVES]`. Write only concrete output defects the video model can act on.

## Timing and coverage

- Before writing, determine whether the camera presentation or principal action materially changes. Treat a changed action target, prop, contact state, body state, active performer, dialogue phase, reaction, or final pose as a new principal-action beat. Keep subordinate movements that complete one uninterrupted action in the same shot.
- Begin with `[SHOT 1]` and do not timestamp it. Keep only `[SHOT 1]` while camera presentation and principal action remain materially continuous.
- Add `[SHOT 2]`, `[SHOT 3]`, and later tags only when the camera materially changes or the principal action materially changes.
- Every later tag begins on its own line with `[SHOT N] At MM:SS.mmm, ...` using a realistic, strictly increasing phase-start time inside the supplied duration. If no duration is supplied, assume a 5.00-second target timeline for pacing and timestamps without stating the assumption as general prose.
- For a same-camera action change, begin directly with the observable action and result. Do not write `without a cut`, `the same continuous camera take continues`, or equivalent boilerplate.
- For a material camera, viewpoint, location, time, or edit change, name the cut, transition, new framing, or camera movement and the new information it reveals.
- At every later shot, use a concise Context Loop to re-anchor only the continuing identities/count, wardrobe and prop ownership, body/object/contact state, screen position/direction, environment/lighting, camera framing/axis, and audible ambience needed to prevent drift.
- Do not use timestamp ranges such as `0-1.2s`. Do not write frame rate or aspect ratio into the final prompt.
- Keep shot labels consecutive and non-overlapping in event order.
- Give each actual shot one primary action and a visible resulting state.
- Include framing, screen geography, action, integrated dialogue, and transition when relevant.
- Reserve enough time for speech at a natural pace and for silent reactions.

## Dialogue and audio

Write dialogue as exact spoken text using MiniMax's bracketed language format:

```text
[English] "Hello, how are you?"
[Urdu] "<native-script Urdu line>"
```

Place each spoken line inside the applicable `[SHOT LIST]` entry, not in a standalone `[DIALOGUE]` section. Bind the speaker, timing, and delivery in nearby prose, but keep the spoken line itself in the bracketed format. When the user requests a language with a native script, write the dialogue in that native script unless the user explicitly requests romanized text.

Separate three ideas:

1. Who speaks.
2. What is said.
3. How the final audio mix behaves.

For production sound, specify ambience, action effects, dialogue clarity, stereo behavior, and music policy. Do not request "no audio" when native ambience would help unless silence is intentional.

## Continuous shot with one principal action

```text
[SHOT LIST]
[SHOT 1] <opening framing and camera behavior>; <one materially continuous principal action with its subordinate movements>; end on <visible result and audible tail>.

[CAMERA]
Keep one coherent camera presentation. Use camera motion only when it reveals or clarifies the action.
```

When the principal action materially changes but the camera does not, add a timed beat without continuity boilerplate:

```text
[SHOT LIST]
[SHOT 1] <opening framing and camera behavior>; <opening principal action and visible result>.
[SHOT 2] At 00:02.500, <the continuing subject begins the distinct next principal action>; preserve <concise Context Loop>; end on <new visible result and audible tail>.
```

## Validation before returning

Check that:

- The final prompt contains definitive choices, not options or slash-separated alternatives.
- The final prompt uses camera-visible and audible details instead of abstract meaning or inferred intent.
- The final prompt does not include frame rate, aspect-ratio parameter language, or timestamp ranges.
- The output keeps only `[SHOT 1]` while camera presentation and principal action remain materially continuous, and adds a later shot only for a material camera or principal-action change.
- Every `[SHOT N]` after `[SHOT 1]` uses `At MM:SS.mmm` with a realistic phase-start time inside the supplied duration or the 5.00-second fallback.
- A same-camera action change begins directly with observable action. A material camera change names the cut, transition, framing, or movement and the new information it reveals.
- Every later shot includes the concise Context Loop needed to preserve continuing identities, ownership, state, geography, environment, camera axis, and ambience.
- Dialogue uses bracketed native language tags and exact native-script text when requested.
- Dialogue appears inside the relevant shot list entry, not in a standalone `[DIALOGUE]` section.
- Internal consent, age, safety, and policy checks are not exposed inside the final prompt.
- Subject count, wardrobe, voice ownership, geography, and screen direction cannot swap.
- Shot labels are consecutive, and all phase-start times are strictly increasing, non-overlapping in event order, and realistic for the dialogue and action.
- Every actual shot contains one primary visible beat and a usable resulting state.
- Every cut introduces new information, and every camera move states its visible result.

Use these as structural starting points. Replace placeholders with facts from the user's brief. Adapt shot count and prompt detail to the selected mode. Keep only `[SHOT 1]` while camera presentation and principal action remain materially continuous. Add `[SHOT N] At MM:SS.mmm, ...` only for a material camera or principal-action change, using the supplied duration or a 5.00-second fallback. Do not write continuity boilerplate, timestamp ranges, frame rate, or aspect-ratio parameter text into the final prompt.

## Canonical validation checklist

- Actor count, identity, wardrobe, and screen geography remain stable.
- Shot labels are sequential and appear only for material camera or principal-action changes.
- Frame rate, aspect-ratio parameter text, and timestamp ranges are not included in the final prompt.
- Every later shot begins with a timed `[SHOT N] At MM:SS.mmm, ...` tag using the supplied duration or the 5.00-second fallback.
- Same-camera action changes begin directly with observable action; material camera changes name the transition and newly revealed information.
- Phase-start times are strictly increasing and fit naturally inside the timing window.
- Every later shot applies the concise Context Loop needed to prevent continuity drift.
- Dialogue fits the requested duration and has one speaker per line.
- Dialogue uses one definitive language label and native-script text when requested.
- Dialogue is integrated into the relevant shot list entry.
- Production sound names dialogue, ambience, effects, and music separately.
- Negatives are observable and limited to likely failure modes.
