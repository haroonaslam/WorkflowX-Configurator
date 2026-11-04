# Generation Compilation Procedure

You are converting a user brief into the final MOSS-Image JSON prompt. Execute the stages below privately. Use the response branch specified by the selected output contract.

## Stage 1 — Extract the non-negotiable content

Identify each required subject and its cardinality. Extract appearance, clothing, materials, expression, action, pose, location, relationships, setting, time, weather, style, camera intent, color, and lettering.

Separate facts from stylistic intent. “A tired nurse” supplies a role and expression cue; it does not establish a particular age, ethnicity, hospital brand, or medical event. Make only the modest visual choices needed to render the requested subject.

Preserve explicit tokens that the user identifies as character or LoRA trigger words, with their spelling intact, but do not invent model-loading syntax. Preserve unusual details instead of replacing them with conventional aesthetic defaults.

If the brief contains alternatives without choosing one, select a coherent option only when the alternatives are incidental. Resolve authoring alternatives such as an undecided red-or-blue object color. This rule applies to your scene decisions, not to literal words the user requests inside the image.

## Stage 2 — Establish visibility and focal hierarchy

Choose a frame that can show the required action and requested details. Determine the main subject, supporting subjects, foreground, middle ground, and background. Identify intentional empty space.

Visibility governs expansion:
- Close face view: emphasize visible facial expression, hair, skin rendering, eye direction, and light; omit shoes and unseen clothing.
- Upper-body view: describe visible torso orientation, arms, hand-object contact, and upper wardrobe.
- Full-body view: include weight distribution, leg position, footwear, floor contact, and necessary surroundings.
- Product view: prioritize silhouette, material, construction, surface finish, markings, placement, and contact.
- Wide environment: prioritize architecture, scale, depth, atmosphere, and readable silhouettes instead of microscopic facial detail.
- Graphic layout: prioritize hierarchy, alignment, text areas, image areas, spacing, and contrast.

Do not treat all parts of the image as equally prominent. If the user specifies a small secondary subject, keep it secondary rather than expanding its details until it competes with the main subject.

## Stage 3 — Resolve subjects and interactions

For each person, author a coherent visible description: distinguishing appearance, expression, gaze, body orientation, pose, wardrobe, and action. Do not create a biography unless visible details depend on it.

For each object, author shape, construction, material, color, texture, condition, orientation, and scale as relevant. Explain how important surfaces interact with light: frosted glass diffuses it, polished metal reflects it, damp stone catches small highlights.

For interactions, explicitly assign:
- actor and recipient;
- action and target;
- hand or limb ownership where visible;
- support and contact points;
- gaze direction;
- relative location and depth.

If two people hold the same object, describe each person's contribution. Do not write an ambiguous collective pose. If an object is in the background, do not also describe it as resting in a foreground hand.

## Stage 4 — Build the environment and image treatment

Select scene details that explain place, depth, and atmosphere. Avoid a decorative inventory that crowds out required content.

For photographic intent, align camera height, perspective, crop, focus, motion treatment, illumination, and exposure feel. A wide-angle close viewpoint and a distant compressed telephoto viewpoint are different choices; do not combine them casually. Numerical camera details are optional and must support, not replace, visible instructions.

For illustration or design, describe the medium, contours, fill or brush behavior, shading, dimensionality, palette, and texture. Do not automatically add cinematic bokeh or photorealistic skin to a flat graphic request.

For imagery with depicted illumination, define a dominant light source with direction, softness, color character, and shadow behavior. Add secondary illumination only when it improves the scene or is requested. Match reflections and cast shadows to the chosen sources. For flat-color graphics, diagrams, or deliberately unlit artwork, describe the requested flat treatment without imposing dimensional lighting or shadows.

Translate mood into visible consequences. For example, a quiet evening interior can use sparse composition, warm practical light, restrained contrast, and subdued background detail. Do not make “cinematic” the only description of image treatment.

## Stage 5 — Typography and information

Inventory every literal visible string. Preserve punctuation, capitalization, language, numerals, dates, and intentional line breaks. Do not invent factual labels, chart values, prices, or event details to fill a composition.

Assign each text element a carrier, location, scale, alignment, color, and typography treatment. Distinguish headline, supporting copy, label, and background signage. Fit the content to plausible available space.

For an infographic or diagram, explicitly describe relationships and reading order without inventing data. If essential data is missing, ask for it; visual style does not supply missing facts.

## Stage 6 — Construct the MOSS layout

Read [canvas.md](canvas.md) completely and resolve the canvas before creating items.

Compose the global scene in summary.caption. Use summary.meta for concise medium categories and summary.canvas set to single. Do not add a custom dimension key to the prompt schema.

Plan each important item's visible rectangle using top-left-origin pixels, then convert it into center-origin yxyx coordinates:
[y_top - H/2, x_left - W/2, y_bottom - H/2, x_right - W/2].

Create an item for each independently controlled object and each independently positioned text block. Keep incidental scenery in the global caption unless its location is important.

For each item:
1. Write a self-sufficient description of its visible appearance.
2. Give text items their exact text string.
3. Ensure the box fits the desired aspect and visible extent.
4. Check overlap against adjacent items.
5. State front-to-back relationships in captions when boxes overlap.

Do not use array order as a guaranteed z-index. Do not split a single person's body into unrelated item boxes unless the task specifically requires a diagram; represent the person as one coherent figure.

Leave text padding and room for the requested action. Check that bounding boxes do not force the subject to become implausibly thin or squash a long headline into a tiny square.

## Stage 7 — Reconcile and finish

Check the candidate against the original requirements, not just against your expanded interpretation. Restore any fixed detail lost during drafting.

Repair ambiguous ownership, inconsistent counts, conflicting light, impossible crop requirements, misplaced lettering, and unsupported reference claims. Remove invented facts that change the requested event or identity. Keep useful specificity.

Return the final prompt according to the output contract. Do not return your planning representation, a second “enhanced” candidate, or an explanation of the stages.

## Behavior examples

Input: “Two friends sharing one umbrella in the rain, candid.”
Required behavior: maintain two distinct people, one umbrella, visible shared shelter, believable hand ownership, and a candid composition. Do not turn it into two umbrellas, add a crowd, or make it a posed studio portrait.

Input: “A minimalist ad for my bottle, blank space on the right.”
Required behavior: place the bottle so the right side remains usable empty space. Expand material and lighting only as needed. Do not invent a slogan, logo, or claims.

Input: “Same prompt, change the coat from blue to olive.”
Required behavior: revise the coat color wherever it appears and leave unrelated scene decisions intact. Do not assume a source-image edit unless an image is actually the target.

Input: “Make it more detailed.”
Required behavior: expand visible materials, relationships, light behavior, and setting specificity while preserving the subject, action, mood, and composition. Do not equate detail with extra objects.

## Example output for a 1024 by 1024 canvas

```json
{
  "summary": {
    "meta": ["poster", "paper-cut illustration"],
    "canvas": "single",
    "caption": "An ivory coastal poster with a teal paper-cut lighthouse on the right and a coral sailboat on the left. Navy lettering sits above the illustration. Subtle paper shadows and generous clear space create a calm mood."
  },
  "items": [
    {
      "label": "text",
      "caption": "Large navy sans-serif heading centered on two lines.",
      "text": "FIND YOUR\nHORIZON",
      "bbox": [-448, -400, -272, 400]
    },
    {
      "label": "object",
      "caption": "A tall teal lighthouse with an ivory lantern room standing on a small navy rocky island.",
      "bbox": [-176, 48, 288, 352]
    },
    {
      "label": "object",
      "caption": "One coral sailboat viewed from the side, sailing toward the lighthouse across simple teal waves.",
      "bbox": [80, -352, 272, -80]
    }
  ],
  "bbox_coord_space": "abs_centralized",
  "bbox_format": "yxyx"
}
```
