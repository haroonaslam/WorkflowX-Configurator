Open-world refinement rule: custom JsonX paths and values are valid prompt content.
- Preserve a coherent custom leaf or subtree when it expresses a concept not covered by the draft's catalog-derived structure.
- Do not delete, flatten, or replace custom content merely because it is not a preset value.
- Keep catalog leaves scalar; move a justified nested expansion beside the leaf as a `<leaf>_details` custom subtree.
- When adding an uncovered detail, use the closest logical parent, descriptive lower_snake_case keys, atomic natural-language values, and the same concise visual wording style as the rest of the prompt.
