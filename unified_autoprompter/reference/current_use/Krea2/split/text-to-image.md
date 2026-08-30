# Krea 2 Text to Image

## Prompt construction sequence

1. Identify the irreducible user intent.
2. Lead with subject and action.
3. Establish environment and composition.
4. Name medium, style, camera, and lighting.
5. Add palette, materials, texture, and atmosphere.
6. Add exact quoted text and fidelity-critical details.
7. Remove contradictions, generic filler, and unsupported invention.

## Compact example pattern

```text
An immense rocket launch exhaust seen from extremely close range, the lower frame filled by incandescent white-orange flame and turbulent translucent heat distortion, soot-dark mechanical edges barely visible above, documentary aerospace photography, hard contrast, dense vapor rolling sideways across the launch platform, granular high-speed capture texture.
```

The example demonstrates expansion structure rather than mandatory vocabulary.

## Validation checklist

- Original intent remains recognizable.
- Subject, action, setting, and composition are complete.
- Style, camera, lighting, palette, and materials agree.
- Spatial relationships and ownership are clear.
- Visible text is exact and quoted.
- Structured output uses the exact top-level fields and keeps `background` before `elements`.
- Every non-text element uses `type: "obj"`; only visible lettering uses `type: "text"`.
- Every structured bbox uses `[x_min,y_min,x_max,y_max]` in normalized 0–1000 coordinates with increasing bounds.
- Detail matches the shot scale.
- The prompt contains no process explanation or generation settings.
