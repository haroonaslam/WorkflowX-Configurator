Apply the selected Common and generation-type guidance to the user's request.

Return only one valid JSON object with exactly these top-level keys:

```json
{
  "positive": "the complete final LTX 2.3 positive prompt, ready to use, with no heading or explanation",
  "negative": "the complete final negative prompt only"
}
```

Do not return Markdown fences, analysis, process commentary, alternative prompts, or additional keys. Keep negative content entirely inside `negative` and do not mix it into `positive`.

Limit the negative to concrete video failures such as blur, jitter, temporal inconsistency, identity drift, distorted anatomy, frame tearing, unwanted text, subtitles, logos, watermarks, overlays, or artifacts.
