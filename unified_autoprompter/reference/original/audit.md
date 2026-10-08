# Prompt coherence audit

Refine only the supplied candidate prompt. Do not regenerate it, expand its creative scope, reinterpret its goal, or convert it to a different format. Make the smallest localized edits needed to correct genuine physical, visual, spatial, descriptive, or temporal contradictions. If no correction is needed, return the candidate unchanged.

Check composition and crop, viewpoint, subject and object placement, anatomy and pose, support and contact, occlusion, perspective, scale, lighting direction, shadows, reflections, material behavior, and—when the prompt describes video—identity, action, camera, audio, and scene continuity.

Preserve every fixed fact, identity, subject and object count, exact rendered text, exact dialogue, reference token, heading, field name, key order, array shape and length, shot order, timestamp, positive/negative separation, and output structure. Do not add or remove sections, keys, list items, subjects, objects, shots, alternatives, metadata, commentary, or explanations. Do not repair ambiguity by inventing visibility or new scene content.

Return only the refined prompt in the same structure as the candidate. Do not add Markdown fences, an audit report, analysis, labels, or introductory text that were not already present.
