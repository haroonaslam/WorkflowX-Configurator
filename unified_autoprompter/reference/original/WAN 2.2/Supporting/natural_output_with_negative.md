Apply the selected Common and generation-type guidance to the user's request.

Return only one valid JSON object with exactly these top-level keys:

```json
{
  "positive": "the complete final WAN 2.2 positive prompt, ready to use, with no heading or explanation",
  "negative": "the complete final negative prompt only"
}
```

Do not return Markdown fences, analysis, process commentary, alternative prompts, or additional keys. Keep negative content entirely inside `negative` and do not mix it into `positive`.

Limit the negative to concrete video failures such as flicker, jitter, stutter, warped motion, identity drift, bad anatomy, frame tearing, unwanted text, subtitles, logos, watermarks, overlays, or artifacts.
