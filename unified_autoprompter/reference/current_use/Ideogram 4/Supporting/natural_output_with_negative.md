Apply the selected Common and generation-type guidance to the user's request.

Return only one valid JSON object with exactly these top-level keys:

```json
{
  "positive": "the complete final Ideogram 4 positive prompt, ready to use, with no heading or explanation",
  "negative": "the complete final negative prompt only"
}
```

Do not return Markdown fences, analysis, process commentary, alternative prompts, or additional keys. Keep negative content entirely inside `negative` and do not mix it into `positive`.

Keep the negative concise and limited to unwanted visible artifacts, incorrect text, anatomical errors, layout failures, blur, unwanted marks, or other concrete failures relevant to the requested image.
