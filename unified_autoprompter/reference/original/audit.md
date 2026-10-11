# Prompt coherence audit

Perform a constrained coherence revision of the supplied candidate prompt. This is a refinement pass, not a new creative interpretation: preserve its goal, fixed facts, requested content, and output contract, while making every change necessary to produce a physically, spatially, visually, and temporally coherent prompt.

Use the minimum scope of change that fully resolves each detected problem. A correction may be local, but do not limit the revision to cosmetic wording or isolated edits when an issue requires coordinated changes across multiple sentences, fields, shots, or timestamps. You may clarify, reorder, or replace conflicting descriptive language and may revise invented or non-binding details. Do not expand the creative scope, add a competing subject or event, or silently change a fixed fact. If the candidate is already coherent, return it unchanged.

## Audit method

Reconstruct the intended result before revising it:

1. Establish the viewpoint, camera position, framing, crop boundaries, depth order, focal hierarchy, and major subject/object placements.
2. For each person or creature, account for every relevant limb and body segment as visible, partially visible, occluded, or outside the crop. Check joint continuity, plausible reach, pose mechanics, balance, center of mass, support, contact points, weight, tension, and gravity.
3. Check that occluders are in front of what they hide; overlaps, held objects, clothing, furniture, and body contacts do not float, fuse, duplicate, intersect impossibly, or contradict stated visibility.
4. Check perspective, horizon and vanishing direction, relative scale, background geometry, depth of field, mirrors, reflective surfaces, screens, and any secondary view for agreement with the primary scene.
5. Check light direction, shadow placement, contact shadows, reflections, material response, translucency, wetness, fabric behavior, and other surface interactions for mutual consistency.
6. Enforce framing contracts. Do not describe details outside the crop as visible; full-body or full-length framing includes the complete figure through both feet with surrounding margin unless the candidate explicitly defines another convention.
7. For video or multi-shot prompts, check identity, wardrobe, props, handedness, location, action state, motion direction, camera direction, lighting, time, dialogue, audio, shot order, and cause-and-effect continuity across every beat.
8. Run a final contradiction scan across the whole candidate after corrections, including positive and negative instructions where both exist.

## Preservation contract

Preserve every fixed fact, identity, subject and object count, exact rendered text, exact dialogue, reference token and role, heading, field name, key order, array shape and length, list-item count, shot order, timestamp, positive/negative separation, and overall output structure. Explicit candidate instructions override inferred corrections. Do not add or remove sections, keys, array items, list items, subjects, objects, shots, alternatives, metadata, commentary, or explanations.

Resolve ambiguity conservatively. Do not invent off-frame visibility or new scene content merely to explain an inconsistency. When a conflict cannot be fully repaired without violating a fixed fact or the output structure, preserve the fixed fact and make the least invasive coherent revision available within that contract.

Return only the refined prompt in the same format and structure as the candidate. Do not add Markdown fences, an audit report, analysis, labels, or introductory text that were not already present.
