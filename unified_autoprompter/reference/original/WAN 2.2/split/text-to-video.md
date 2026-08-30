# WAN 2.2 Text to Video

## Generation type

- **Text to video:** construct the complete moving scene from text.

### Action and temporal development

Turn a static idea into a causal movement sequence. Establish the opening state, principal action, intermediate change when needed, and usable final state. Keep motion physically plausible and proportionate to clip length. Do not overload a short clip with unrelated actions.

## Text-to-video method

Because no image defines the opening state, describe the complete visual world.

1. Lead with subject, principal action, and environment.
2. Establish shot scale, viewpoint, and visual style.
3. Describe the action in chronological order.
4. Add motivated camera behavior.
5. Add lighting, palette, texture, atmosphere, and background motion.
6. Finish with the final visible state.

Do not assume any subject appearance, setting, or composition exists outside the text. If the input is short, infer compatible production detail without changing the premise.

### T2V expansion rules

Apply these requirements:

1. Preserve the original subject and action. Enrichment must not replace the premise.
2. Select no more than four suitable cinematic settings when the brief does not already decide them. Categories include time, light source, light intensity, light angle, color tone, shot size, camera angle, and composition. It is unnecessary and usually harmful to choose from every category.
3. When time is unspecified, use daylight. When shot size is unspecified, prefer a medium or wide shot. When composition is unspecified, use centered composition.
4. Select light sources from scene logic: daylight, artificial light, moonlight, practical light, firelight, fluorescent light, overcast light, or sunny light. Name the actual source where useful, such as a window, lamp, flame, or sky.
5. Light intensity is soft or hard; light direction may be top, side, under, or edge light; color treatment may be warm, cool, or mixed.
6. Shot vocabulary includes medium, medium close-up, wide, medium wide, close-up, extreme close-up, and extreme wide. Camera-angle vocabulary includes over-the-shoulder, low angle, high angle, Dutch angle, aerial, and overhead.
7. Do not add a static camera angle when the original request already specifies camera movement and the two would compete.
8. Complete visible subject traits—appearance, expression, count, ethnicity when explicitly supported, and pose—without introducing a new person into a landscape or object-only request. Add compatible background detail.
9. Do not add literary claims about what the image symbolizes or how it “feels.” Express tone through visible light, color, performance, weather, and composition.
10. Expand each action into an observable motion process. When the source is static, add a modest subject or environmental motion that serves the scene, such as body sway, moving clouds, or leaves reacting to wind.
11. If the user supplies no style, do not invent one. If a style is supplied, place it first. If the style is explicitly non-photographic—such as 2D illustration—do not force incompatible live-action cinematic language onto it.
12. When a sky is described, prefer a clear blue sky to reduce overexposure; override this when the user explicitly requests another sky, time, weather, or palette.
13. Produce one direct English prompt with enough detail to express the intended scene, with no “rewritten prompt” heading or explanation.

Compact pattern:

```text
A lone cyclist in a yellow rain jacket crosses a wet suspension bridge at blue hour; a wide tracking shot moves parallel to her as wind drives fine rain through the cables, city lights smear across the river below, and the camera gradually closes to a medium profile while her jacket snaps in the gusts.
```

## Timing and shot logic

Use one continuous shot when camera presentation and principal action remain materially continuous. Introduce a new shot or timed beat when the camera materially changes or the principal action changes enough to require a separate phase. If duration is known, distribute action and dialogue realistically across it. If duration is absent, describe chronological phases without inventing frame-accurate timing.

Every cut should reveal a new subject, state, viewpoint, space, or time. Prefer camera motion over a cut when only distance or angle changes.
