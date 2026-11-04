Apply the selected Common and generation-type guidance to the user's request.

Return only one valid JSON object with exactly these top-level keys:

```json
{
  "prompt_json": {"complete FIBO 2 prompt object": "matching the canonical FIBO 2 schema defined in the selected profile guide"},
  "negative": ""
}
```

Replace the placeholder object with the complete final FIBO 2 prompt object. Preserve the canonical field names and ordering. For generation, `prompt_json` must contain the native shared caption fields and no `edit_instruction`. For editing, preserve either supported native envelope: root caption fields beside `edit_instruction`, or `structured_caption` beside `edit_instruction`. Do not duplicate the same caption in both forms. Do not return Markdown fences, analysis, additional wrapper keys, or negative content. The `negative` value must be the empty string.
