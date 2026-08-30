Apply the selected Common and generation-type guidance to the user's request.

Return only one valid JSON object with exactly these top-level keys:

```json
{
  "positive": "the complete final SDXL prompt, ready to use, with no heading or explanation",
  "negative": ""
}
```

Do not return Markdown fences, analysis, process commentary, alternative prompts, or additional keys. Do not invent or output negative content. The `negative` value must be the empty string.
