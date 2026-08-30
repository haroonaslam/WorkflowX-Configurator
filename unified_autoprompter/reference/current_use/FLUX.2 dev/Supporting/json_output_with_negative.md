Apply the selected Common and generation-type guidance to the user's request.

Return ONLY valid JSON with this wrapper object:
{
  "prompt_json": {
    "scene": "overall scene description",
    "subjects": [{"description": "subject description", "position": "where in frame", "action": "what the subject is doing"}],
    "style": "artistic or photographic style",
    "color_palette": ["#RRGGBB"],
    "lighting": "lighting description",
    "mood": "emotional tone",
    "background": "background details",
    "composition": "framing and layout",
    "camera": {"angle": "camera angle", "lens": "lens type", "depth_of_field": "focus behavior"},
    "text": [{"content": "literal text if any", "placement": "where it appears", "typography": "style, size, color"}]
  },
  "negative": "downstream-only negative/NAG helper prompt; FLUX.2 itself does not natively use negative prompts"
}
The prompt_json value must be the final structured FLUX.2 dev prompt object, not a string. Keep field values concise, concrete, and production-oriented.
