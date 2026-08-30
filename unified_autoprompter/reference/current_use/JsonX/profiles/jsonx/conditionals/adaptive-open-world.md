Preset coverage rule: the JsonX preset catalog is authoritative guidance, not a closed vocabulary.
- First use an exact catalog value when it faithfully expresses the requested or observed concept.
- Otherwise use a semantically close value only when it preserves the specific meaning; never force a merely similar preset that changes, weakens, or generalizes the intent.
- When the correct catalog path exists but none of its preset values is suitable, keep that path and write a concise, deterministic custom natural-language value in the same descriptive style as neighboring preset values.
- A catalog leaf is scalar. When a concept needs nested children beneath a catalog scalar leaf, keep the catalog leaf scalar when applicable and put the expansion in a sibling `<leaf>_details` custom subtree; for example, use `scene.environment_details.*`, not an object inside `scene.environment`.
- When no suitable catalog path exists, place the concept beneath the closest logical JsonX parent and create the smallest coherent nested branch needed to express it. Use descriptive lower_snake_case keys and natural-language visual values; never invent preset IDs or ID-like keys.
- Preserve deep tree structure for custom content. Split independent attributes into separate leaves instead of packing uncovered details into one catch-all string.
- Never omit a requested, visible, or strongly implied concept merely because the preset catalog does not contain it. Reason from the instructions and image, while respecting visibility, coherence, and the prompt-only contract.
