Apply the selected Common and generation-type guidance to the user's request.

Return only the final MiniMax H3 Official prompt body as plain text in the exact field or bracketed-section structure required by the selected generation-type guide. Do not return JSON, Markdown fences, wrapper keys, analysis, assumptions, watch-outs, positive labels, or a separate negative prompt.

Do not generate a separate node negative output. Any target-native section whose literal name contains `NEGATIVES` remains part of the positive MiniMax H3 Official prompt body rather than a separate negative field.
