Template Fill refinement constraint:
- Improve only coherence, specificity, and wording of existing populated scalar leaves.
- Preserve the populated Stage 1 hierarchy and every existing path. Do not rename, move, flatten, wrap, or add branches.
- You may set an existing leaf to JSON `null` only when it is clearly contradictory, impossible, or unsupported. Omitted paths are treated as unchanged.
- Return the complete refined prompt object.
