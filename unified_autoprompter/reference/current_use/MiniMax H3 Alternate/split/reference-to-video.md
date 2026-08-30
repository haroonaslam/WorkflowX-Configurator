# MiniMax H3 Alternate Reference to Video

## Generation type

Use ordered image, video, or audio references for bounded reference generation, motion/performance transfer, or voice transfer.

## Supported reference operations

- **Omni Reference:** one or more image, video, or audio assets define the result.
- **Performance transfer:** a video supplies motion, expression, action order, singing, or camera behavior while other media supply identity or voice.
- **Voice transfer:** audio supplies timbre, accent, cadence, singing, or delivery for a named target.

## Omni reference scene

```text
[REFERENCE USE]
<Picture 1> defines <Character A>'s face, hair, body, and wardrobe only. Do not inherit its pose, action, expression, framing, background, environment, lighting, camera, text, audio, surrounding people, or unrelated objects.
<Picture 2> defines <Character B>'s face, hair, body, and wardrobe only. Do not inherit its pose, action, expression, framing, background, environment, lighting, camera, text, audio, surrounding people, or unrelated objects.
<Picture 3> defines the location, layout, materials, and lighting only. Do not inherit its people, identities, bodies, wardrobe, actions, props, dialogue, sound, text, or camera unless explicitly assigned.

[IDENTITY / CONTINUITY LOCKS]
Keep exactly two characters. Preserve identity, wardrobe, body proportions, and voice ownership. No face, clothing, or position swaps.

[SCENE]
<Location and time>. <Character A> wants <objective>; <Character B> resists because <conflict>. The scene moves from <starting emotion> to <ending emotion>.

[SCREEN GEOGRAPHY]
<Character A> begins frame left. <Character B> begins frame right. Maintain the axis and matching eyelines.

[SHOT LIST]
[SHOT 1] <framing>; <camera>; <action>; <Character A> says with <delivery>: [<Language>] "<Exact native-script line.>"; end on <visible state>.
[SHOT 2] At 00:02.000, the camera cuts to <new framing that reveals new information>; <reaction or escalation>; <Character B> replies with <delivery>: [<Language>] "<Exact native-script line.>".
[SHOT 3] At 00:04.000, the shot cuts to <new viewpoint or state>; <resolution>; end with <stable final tableau and audible tail>.

[ACTING]
<Posture, breath, gaze, gesture, listening behavior, and emotional progression.>

[LIGHT AND IMAGE]
<Lighting, palette, texture, lens character, and depth of field.>

[CAMERA]
<Allowed movement, shot sizes, axis, and transition language.>

[PRODUCTION SOUND]
Native stereo <ambience>. Dialogue remains clear. Include <motivated effects>. <Music rule>.

[NEGATIVES]
No extra people, face drift, wardrobe changes, voice swaps, broken eyelines, duplicate props, subtitles, or unmotivated cuts.
```

## Mode contract

- **Performance transfer**: State that the source video controls only named motion, performance, timing, or camera traits. Explicitly reject its actors, clothing, location, and identity unless needed.
- **Complex motion path**: Write the ordered position changes explicitly and lock subject count, camera, and final arrangement.

## Motion and camera transfer

```text
[REFERENCE USE]
<Picture 1> defines <Character A>'s identity and wardrobe only. Do not inherit its pose, action, expression, framing, background, environment, lighting, camera, text, audio, surrounding people, or unrelated objects.
<Picture 2> defines <Character B>'s identity and wardrobe only. Do not inherit its pose, action, expression, framing, background, environment, lighting, camera, text, audio, surrounding people, or unrelated objects.
<Video 1> defines body motion, expression timing, interaction rhythm, and camera movement only. Do not inherit its actors, identities, bodies, wardrobe, location, props, dialogue, sound, or visual style.

[TRANSFER]
Recreate the complete action order and camera behavior from <Video 1> with <Character A> and <Character B>. Preserve every handoff, pause, direction change, contact, occlusion, and final position.

[CONTINUITY]
Keep exactly two people. Preserve identity, wardrobe, screen direction, and left/right geography. Make weight, contact, hair, fabric, lighting, and shadows physically believable in <target scene>.

[SOUND]
Use native stereo ambience and synchronized action effects. <Dialogue or music rule.>

[NEGATIVES]
No actor leakage from <Video 1>, identity swaps, missing action beats, extra cuts, or position reversals.
```

## Mode contract

- **Voice transfer**: Bind the audio to one named character and exact line. Preserve lip sync, voice ownership, and native stereo ambience.

## Voice transfer with exact dialogue

```text
[REFERENCE USE]
<Video 1> defines the target character, visible performance, scene, camera, and clip structure.
<Audio 1> defines only <Character A>'s voice timbre, accent, cadence, and emotional delivery.

[SHOT LIST]
[SHOT 1] Preserve the visible performance and scene; <Character A> says with <accent, pace, volume, breath, and emotional restraint>: [<Language>] "<Exact native-script line>."; keep the spoken line synchronized with the mouth movement and action.

[SYNC AND MIX]
Preserve accurate lip sync and the same character identity. Keep native stereo room tone and motivated effects under clear dialogue. No extra speech, subtitles, voice drift, or background music unless requested.
```

## Reference-based generation guide

Do not repeat the full reference map inside later-shot Context Loops.

Turn a scene brief and ordered media into one copy-ready MiniMax H3 prompt. Treat every reference as a bounded source of authority, place stable truths before action, and make every shot describe framing, screen geography, performance, integrated dialogue, and visible end state.

When the user leaves a model-facing choice unclear, choose one definitive value that best fits the brief and references.

Infer harmless production details when the user's intent is clear. Ask only when a missing answer would change reference order, identity ownership, source-master selection, exact dialogue, or story outcome.

State dialogue as exact bracketed-language lines inside the applicable shot, such as `[Urdu] "<native-script line>"`. Name accent, delivery, and timing in prose outside the quoted spoken line. Keep dialogue separate from the reference-audio role and the final audio mix.

Separate four ideas:

1. Who speaks.
2. What is said.
3. Which reference supplies the voice or delivery.
4. How the final audio mix behaves.

## 2. Build an internal authority map

For every asset, record:

1. Exact reference token, normally `<Picture 1>`, `<Video 1>`, or `<Audio 1>`.
2. Named subject or production role.
3. Attributes it controls.
4. Incidental attributes it must not impose.

Assign narrow, truthful roles such as identity, wardrobe, prop, scene, style, motion, performance timing, camera, edit rhythm, voice, music, or sound effect. Never let "use the references" stand in for a map.

Use the exact MiniMax reference labels in final prompt text: `<Picture 1>`, `<Picture 2>`, `<Video 1>`, `<Video 2>`, `<Audio 1>`, and `<Audio 2>`. When a supplied binding map provides different exact labels, preserve those labels and their attachment order exactly; do not infer tokens from visible library labels, filenames, symbols, or UUIDs. Do not renumber references silently. Map each character and voice individually; never rely on "respectively."

Use only reference tags genuinely available to the request. Treat a reference as available when it is already attached, supplied with the request, or mentioned by the user as a reference role for the same generation request and its media type and order are unambiguous. If the user mentions an audio reference and no other audio references are in play, bind it as `<Audio 1>`. Never invent unavailable tags from vague intent, filenames, visible library labels, symbols, or UUIDs. If reference order is ambiguous, ask a concise clarification before writing the final prompt.

For every reference, state both its positive authority and its exclusion boundary. A subject image controls only the assigned identity, body, wardrobe, prop, scene, style, or other named attributes; it must not contribute pose, action, expression, framing, background, environment, lighting, camera, text, audio, surrounding people, or unrelated objects unless assigned. A motion or camera reference controls only its named motion, timing, performance, framing, edit, or camera traits; it must not contribute actors, identities, bodies, wardrobe, location, props, dialogue, sound, or visual style unless assigned.

## Reference truth

Put these sections before the shot list when relevant:

```text
[REFERENCE USE]
[IDENTITY / CONTINUITY LOCKS]
[SCENE]
[SCREEN GEOGRAPHY]
```

## Canonical reference syntax

Use numbered tokens in upload order. When an ordered binding map is supplied, that map is the source of truth:

```text
<Picture 1>
<Picture 2>
<Video 1>
<Audio 1>
```

Use `<Picture N>`, `<Video N>`, and `<Audio N>` labels for references in final prompt text. Do not add an `@` prefix. If the supplied binding map uses a different exact token, preserve it. Never guess reference contents. When attachments are unavailable, write role placeholders or explicitly state assumptions.

A reference label may be used when the asset is already attached, supplied with the request, or mentioned by the user as a reference role for the same generation request with unambiguous media type and order. If the user mentions an audio reference and no other audio references are in play, use `<Audio 1>` for that audio role. Do not invent labels from vague future intent or unclear ordering; ask a concise clarification before writing the final prompt when reference order is ambiguous.

For every reference, name:

```text
<token> defines <subject or production role>'s <attributes> only.
Do not inherit <incidental people, background, pose, framing, clothing, sound, or style>.
```

Useful authority roles:

- **Image**: identity, wardrobe, prop appearance, product geometry, location, layout, material, lighting, graphic style.
- **Video**: motion path, body mechanics, performance timing, expression order, camera movement, framing, edit rhythm, transition language, soundscape.
- **Audio**: voice timbre, accent, cadence, emotional delivery, singing, music, or a sound effect.

Do not let one reference control unrelated categories unless the user explicitly wants the whole reference reproduced.

For a subject image, explicitly exclude any unassigned pose, action, expression, framing, background, environment, lighting, camera, text, audio, surrounding people, and unrelated objects. For a motion or camera reference, explicitly exclude any unassigned actors, identities, bodies, wardrobe, location, props, dialogue, sound, and visual style.

## Recommended prompt order

Use the smallest useful subset:

```text
[REFERENCE USE]
[IDENTITY / CONTINUITY LOCKS]
[SCENE]
[SCREEN GEOGRAPHY]
[SHOT LIST]
[ACTING]
[LIGHT AND IMAGE]
[CAMERA]
[PRODUCTION SOUND]
[NEGATIVES]
```

Stable truth precedes action. Finishing direction follows the timed scene.

## Reference validation

- Every reference has one named job and a clear boundary.
- Every identity, voice, prop, and edit target has one owner.
- Reference tokens use the exact MiniMax labels by default: `<Picture N>`, `<Video N>`, and `<Audio N>`. All tokens match attachment order and are used consistently.
- The final prompt uses only reference roles available to the selected mode.
- The final prompt uses only reference tags that are attached, selected, or mentioned by the user for the same request.
- Incidental backgrounds, people, poses, or styles are excluded when leakage is plausible.
- Camera, lighting, acting, dialogue, production sound, and negatives do not contradict the references.
- The prompt does not invent unsupported facts about an unseen reference.

## Canonical reference checks

- Reference order and tokens are exact, with references written as `<Picture N>`, `<Video N>`, and `<Audio N>` unless the supplied binding map requires another token. Tokens correspond to attached, selected, or user-mentioned references for the same request.
- Every reference has one named authority and an exclusion boundary.
- Subject, prop, and voice ownership are explicit.
- Camera and edit language do not fight the reference motion.

Use these as structural starting points. Replace placeholders with facts from the user's references and brief. Adapt shot count and prompt detail to the selected mode. Keep only `[SHOT 1]` while camera presentation and principal action remain materially continuous. Add `[SHOT N] At MM:SS.mmm, ...` only for a material camera or principal-action change, using the supplied duration or a 5.00-second fallback. Do not write continuity boilerplate, timestamp ranges, frame rate, or aspect-ratio parameter text into the final prompt.

## Canonical mode declarations

- **Omni Reference**: one or more image, video, or audio assets define the result.
- **Performance transfer**: a video supplies motion, expression, action order, singing, or camera behavior while other media supply identity or voice.
- **Voice transfer**: audio supplies timbre, accent, cadence, singing, or delivery for a named target.
