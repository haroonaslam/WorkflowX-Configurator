# WAN 2.2 Common Rules and Guide

Use only the input modalities and conditioning roles selected for the request.
## Prompt-output hygiene

- Preserve the original subject, action, and requested outcome.
- Return one complete prompt without analysis or alternative versions.
- Add only compatible cinematic and temporal detail.
- Do not expose generation parameters, media metadata, or prompt-construction commentary as scene prose.
- Avoid piling on every possible camera, lighting, and style term; select those that serve the scene.
- Use visible action and physical change rather than abstract plot explanation.

### Subject

Describe subject count, visible appearance, wardrobe, posture, expression, and owned props. Keep identity and attributes stable across the clip. For several subjects, state positions, interactions, gaze, contact, and movement ownership.

### Environment

Add location, time, weather, surfaces, architecture, landscape, props, and background motion. The environment must remain compatible with the user’s premise and should not compete with the focal action.

### Camera

Choose framing, angle, camera movement, and focal behavior that reveal the action clearly. Camera movement should have a visible purpose: follow the subject, reveal new information, tighten on an expression, establish scale, or change the spatial relationship.

Use coherent terms such as static wide shot, handheld medium follow, slow push-in, lateral tracking, pan, tilt, orbit, overhead view, low angle, shallow focus, or deep-focus establishing shot. Avoid incompatible movements within one brief moment.

### Lighting and color

Select time, source, direction, intensity, contrast, saturation, and color temperature that support the requested tone. Keep changes in light causally connected to the action or environment.

### Atmosphere and aesthetic

Use a coherent visual treatment: realistic cinema, documentary, phone footage, commercial, animation, painterly motion, science fiction, period drama, or another specified medium. Reinforce it through palette, texture, lens behavior, movement, and production design.

## Multi-subject and interaction guidance

Name each participant’s position, action, gaze, and contact. State who initiates movement and who reacts. Preserve left/right geography and object ownership. Avoid simultaneous complex actions that obscure the focal event.

## Text and graphics

Video text rendering is less reliable than general scene generation. Keep requested text short, exact, and quoted. State its surface and location. Do not invent additional captions, subtitles, logos, or watermarks.

## Failure repairs

- **Frozen I2V:** add specific subject motion, environmental response, and camera movement.
- **Chaotic action:** reduce simultaneous events and give the clip one principal action.
- **Identity drift:** strengthen appearance authority and reduce conflicting style or motion demands.
- **Camera confusion:** use one movement with a stated visual result.
- **Temporal jump:** add causal intermediate motion or an explicit meaningful cut.
- **Attribute leakage:** bind clothing, props, pose, and motion to their correct source.
- **Prompt drift:** move the original subject and action to the beginning and remove ornamental additions.

## Validation checklist

- The selected mode matches its required conditioning inputs.
- T2I contains no temporal, camera-motion, or audio instructions.
- Original subject and action remain intact.
- Opening state, motion path, and final state are coherent.
- Camera behavior reveals rather than obscures the action.
- Lighting, palette, environment, and style agree.
- Image and motion sources have bounded roles.
- Subject count, identity, clothing, props, and geography remain stable.
- The final prompt contains no prompt-construction or generation-parameter commentary.
- T2V uses no more than four added cinematic setting choices and does not invent an unrequested style.
- I2V concentrates on motion and camera behavior rather than redundantly recaptioning the starting image.
- T2V provides complete scene construction; I2V remains motion-first and avoids redundant static recaptioning.
- Animate separates character appearance from driving performance and distinguishes animation from replacement.
- S2V binds one image identity and one audio timeline while giving actions, expressions, environment, and camera explicit direction.
