# MiniMax H3 Alternate Video to Video

## Generation type

- **Video to Video:** a source video remains the master while named visual or audio elements change.

## Mode contract

- **Targeted edit**: Name one source video as the sole editing master. List exact changes, reference roles, and everything that must remain unchanged.
- **Environment or VFX replacement**: Preserve foreground identity, edges, performance, occlusion, timing, camera, and duration. Require coherent relighting, parallax, shadow, and interaction with the new scene.

## Editing contract

Use this structure:

```text
[SOURCE MASTER]
<Video 1> is the sole editing master for subjects, scene, timeline, camera, occlusions, dialogue, ambience, and event order.

[REFERENCE USE]
<Replacement references and their bounded roles.>

[EDIT]
<Exact target, change, region, or time range.>

[PRESERVE]
<Identity, performance, motion, occlusion, lighting, camera, dialogue, ambience, timing, and untouched objects as needed.>
```

For replacement, keep the source object's motion path, visibility, contacts, occlusions, scale changes, and timing unless the user asks to change them.

## Targeted object or character edit

```text
[SOURCE MASTER]
<Video 1> is the sole editing master for subjects, performance, scene, timeline, camera, occlusions, dialogue, ambience, and event order.

[REFERENCE USE]
<Picture 1> defines only <replacement target>'s appearance, structure, material, and color. Do not inherit its pose, action, expression, framing, background, environment, lighting, camera, text, audio, surrounding people, or unrelated objects.

[EDIT]
Replace only <source target> with <replacement target>. Keep exactly one instance. The replacement inherits every motion path, contact, occlusion, rotation, scale change, speed change, and visibility event from the source target.

[PRESERVE]
Do not change any other subject, object, action, background, light, camera move, cut, dialogue, sound effect, ambience, or duration.
```

## Environment or VFX replacement

```text
[SOURCE MASTER]
<Video 1> defines the foreground subjects, performance, motion, timing, camera, and clip structure.
<Video 2> defines only the target environment, atmosphere, and lighting style.

[EDIT]
Replace <bounded background or effect> in <Video 1> with the target environment from <Video 2>. Make parallax, background motion, shadows, reflections, transmitted light, and interaction respond correctly to the foreground performance.

[PRESERVE]
Keep identity, hair and fabric edges, foreground objects, gesture timing, scale, occlusions, camera, and duration unchanged. No spill, halos, altered performance, or unrelated scene changes.
```

## Edit validation

- Edits name the sole master, exact targets, and preserved content.

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

## Edit preservation check

- Editing protects all untargeted content.

## Canonical mode declaration

- **Targeted edit**: a source video remains the master while named visual or audio elements change.
