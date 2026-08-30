Apply the selected Common and generation-type guidance to the user's request.

Return only one valid JSON object with exactly these top-level keys:

```json
{
  "prompt_json": {"complete Ideogram caption object": "matching the canonical Ideogram schema defined in the selected profile guide"},
  "negative": "the complete final negative prompt only"
}
```

Replace the placeholder object with the complete final Ideogram caption object. Preserve the canonical field names and ordering. Every bbox must use normalized `[y_min,x_min,y_max,x_max]` coordinates from 0 to 1000. Keep negative content entirely outside `prompt_json`. Do not return Markdown fences, analysis, or additional keys.

Keep the negative concise and limited to unwanted visible artifacts, incorrect text, anatomical errors, layout failures, blur, unwanted marks, or other concrete failures relevant to the requested image.
