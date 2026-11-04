Apply the selected Common and generation-type guidance to the user's request.

Return only one valid JSON object with exactly these top-level keys:

```json
{
  "prompt_json": {"complete MOSS-Image prompt object": "matching the canonical MOSS-Image schema defined in the selected profile guide"},
  "negative": ""
}
```

Replace the placeholder object with the complete final MOSS-Image prompt object. Preserve the canonical field names and ordering. The `prompt_json` value must use the native MOSS `summary`, `items`, `bbox_coord_space`, and `bbox_format` structure. Every item bbox must use centered-pixel `[y_min,x_min,y_max,x_max]` coordinates with `bbox_coord_space` set to `abs_centralized` and `bbox_format` set to `yxyx`. Do not return Markdown fences, analysis, additional wrapper keys, or negative content. The `negative` value must be the empty string.
