Apply the selected Qwen Image 2.1 Common, generation-type, and reference-usage guidance to the user's request.

Return only one valid JSON object with exactly these top-level keys:

```json
{
  "positive": "the complete final Qwen Image 2.1 prompt, ready to use, with no heading or explanation",
  "negative": ""
}
```

Do not return Markdown fences, analysis, reasoning, process commentary, alternative prompts, headings, or additional keys. Place the complete natural-language result inside `positive`. Do not place JSON, generation parameters, workflow instructions, or commentary inside the prompt. The `negative` value must be the empty string.
