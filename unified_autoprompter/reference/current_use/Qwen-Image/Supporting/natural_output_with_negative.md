Apply the selected Common and generation-type guidance to the user's request.

Return only one valid JSON object with exactly these top-level keys:

```json
{
  "positive": "the complete final Qwen-Image positive prompt, ready to use, with no heading or explanation",
  "negative": "the complete final negative prompt only"
}
```

Do not return Markdown fences, analysis, process commentary, alternative prompts, or additional keys. Keep negative content entirely inside `negative` and do not mix it into `positive`.

Limit the negative to concrete unwanted outcomes such as unreadable or incorrect text, identity drift, facial or hand distortion, artifacts, watermarks, or unwanted objects.
