Apply the selected Common and generation-type guidance to the user's request.

Return only one valid JSON object with exactly these top-level keys:

```json
{
  "prompt_json": {"complete Krea2 prompt object": "matching the canonical Krea2 schema defined in the selected profile guide"},
  "negative": ""
}
```

Replace the placeholder object with the complete final Krea2 prompt object. Preserve the canonical field names and ordering. Every bbox must use normalized `[x_min,y_min,x_max,y_max]` coordinates from 0 to 1000. Do not return Markdown fences, analysis, additional wrapper keys, or negative content. The `negative` value must be the empty string.
