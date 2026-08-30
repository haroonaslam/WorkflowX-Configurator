Apply the selected Common and generation-type guidance to the user's request.

Return only one valid JSON object with exactly these top-level keys:

```json
{
  "positive": "the complete final SDXL positive prompt, ready to use, with no heading or explanation",
  "negative": "the complete final negative prompt only"
}
```

Do not return Markdown fences, analysis, process commentary, alternative prompts, or additional keys. Keep negative content entirely inside `negative` and do not mix it into `positive`.

Use concise SDXL negative conditioning for unwanted quality, anatomy, geometry, text, crop, watermark, and style-specific failures. Do not restate desired positive content.
