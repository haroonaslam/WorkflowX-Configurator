# MiniMax H3 Alternate First–Last Frame to Video

## Generation type

- **First–Last Frame to Video:** two ordered images define the exact opening and ending boundary frames.

## Mode contract

- **First–Last Frame to Video:** Declare which image is the first frame and which is the last. Describe the smallest plausible causal bridge between them without inventing extra subjects or unnecessary cuts. Keep only `[SHOT 1]` while camera presentation and principal action remain materially continuous; add timed later shots only when either materially changes.

Declare which image is the first frame and which is the last frame.

## First and last frame bridge

```text
[BOUNDARY FRAMES]
<Picture 1> is the exact first frame. Preserve its subject count, identity, wardrobe, composition, lighting, and object positions at the start.
<Picture 2> is the exact last frame. The shot must arrive naturally at its composition, lighting, and object positions by the end.

[ACTION]
In one continuous causal motion, <describe the smallest plausible action that connects the frames>. Keep only `[SHOT 1]` while camera presentation and principal action remain materially continuous. Add a timed later shot only when the camera or principal action materially changes, using the supplied duration or a 5.00-second fallback. Maintain the same subjects and continuous objects throughout.

[CAMERA AND SOUND]
<Camera rule>. Native stereo <ambience and effects>.

[NEGATIVES]
No hard cut, teleportation, duplicate subject, identity change, prop swap, or discontinuous lighting.
```

For First/Last Frame, preserve the source composition.

- For First/Last Frame, preserve one coherent bridge when it can plausibly reach the final frame. Add timed later shots only for material camera or principal-action changes, and make the final shot arrive at the last-frame state by the requested end.

- For First/Last Frame transitions, keep one `[SHOT 1]` when camera presentation and principal action remain materially continuous. Add timed later shots only for material camera or principal-action changes, and make the final shot arrive at the last-frame state by the requested end.

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

## Build an internal authority map

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

## Canonical mode declaration

- **First/Last Frame**: one or two images define boundary frames.
