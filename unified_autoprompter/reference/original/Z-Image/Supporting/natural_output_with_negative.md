Apply the selected Common and generation-type guidance to the user's request.

Return only one valid JSON object with exactly these top-level keys:

```json
{
  "positive": "the complete final Z-Image positive prompt, ready to use, with no heading or explanation",
  "negative": "the complete final negative prompt only"
}
```

Do not return Markdown fences, analysis, process commentary, alternative prompts, or additional keys. Keep negative content entirely inside `negative` and do not mix it into `positive`.

Limit the negative to concrete unwanted failures such as blur, artifacts, distorted anatomy, unreadable text, watermarks, duplicated limbs, or noisy texture.

## Negative prompt content guidance

Build the negative prompt as a concise, comma-separated list of concrete unwanted visual or temporal results.

Select concepts based on the completed positive prompt: its subjects, intended appearance, medium, composition, crop, action, materials, lighting, and motion. Prioritize failures most likely to undermine that specific result.

Use the categorized examples below as candidates. Select relevant concepts and add other specific failures when needed. Do not copy every category or every example.

Preserve the user's intent. Never select a negative concept that suppresses a requested feature, character trait, body type, clothing, pose, style, effect, visible text, or deliberate imperfection. Explicit prompt details take precedence over preset defaults.

Keep each concept brief and specific. Remove duplicates and redundant synonyms. Avoid explanations, instructions, and restatements of the positive prompt.

### Rendering and image clarity

Candidates:

`unintended blur, low-resolution artifacts, loss of surface detail, smeared background details, oversharpening, sharpening halos, excessive artificial clarity, compression artifacts`

Apply these to areas intended to appear clear and resolved. Preserve deliberate motion blur, shallow depth of field, atmospheric softness, grain, and other requested photographic or artistic treatments.

### Photorealistic skin

Candidates:

`plastic skin, waxy skin, rubbery skin, artificial skin texture, oversmoothed skin, airbrushed skin, beauty-filter smoothing, excessive retouching, synthetic surface perfection, missing natural skin texture, unnaturally symmetrical facial features`

Use these for photographic or realistically rendered people, selecting a few representative failures. Preserve intentional makeup, retouching, smooth surfaces, and stylization when requested.

### Anatomy, pose, and proportions

Candidates:

`malformed anatomy, fused anatomy, duplicated body parts, unintended missing limbs, extra limbs, stretched limbs, warped joints, disconnected joints, implausible joint angles, stiff pose, unnatural body contours, incorrect limb proportions, incorrect head-to-body ratio, implausible balance, unsupported body weight`

Match these to the subject's intended anatomy and pose. Preserve specified disabilities, injuries, unusual anatomy, stylized proportions, and deliberate transformations.

Do not treat body parts hidden by clothing, occlusion, or framing as missing anatomy.

### Hands and fingers

Candidates:

`malformed hands, extra fingers, duplicated fingers, fused fingers, disconnected fingers, warped finger joints, implausible grip, incorrect hand-object contact`

Select these when hands are visible or central to an interaction. Use missing-finger concepts only when fingers should actually be visible; a closed fist or partially occluded hand does not require every finger to be shown.

### Feet and toes

Candidates:

`malformed feet, extra toes, duplicated toes, fused toes, disconnected toes, warped ankles, incorrect foot placement, floating feet, incorrect ground contact`

Select foot and ankle failures when stance or visible feet matter. Select toe failures only when toes are exposed and visible. Preserve intentional airborne movement and naturally hidden toes.

### Hair

Candidates:

`solid hair masses, smeared hair edges, artificial hair gloss, hair fused with skin, hair fused with clothing, hair fused with the background, unnaturally repeated hair texture, hair disconnected from the scalp`

Select failures appropriate to the intended hairstyle and medium. Preserve requested wetness, gloss, sculpted shapes, and stylization while excluding unintended fusion or texture artifacts.

### Clothing, fabric, and accessories

Candidates:

`painted-on clothing, clothing fused with skin, weightless fabric, implausible fabric tension, gravity-defying folds, unintended repeated fabric patterns, broken seams, floating accessories, disconnected jewelry, jewelry fused with skin`

Use only for items present in the scene. Preserve intentional patterns, seamless construction, close-fitting garments, wind-driven fabric, and accessories moving naturally with the subject.

### Objects, materials, and spatial relationships

Candidates:

`fused objects, impossible object intersections, unintended duplicated objects, unsupported floating objects, disconnected components, inconsistent object geometry, warped rigid objects, incorrect occlusion, contradictory depth order, inconsistent scale, broken perspective, implausible contact, unnaturally uniform material texture, inconsistent material response`

Select failures that affect the described objects and their relationships. Preserve intended repetition, patterned surfaces, transparency, suspended objects, and deliberate surreal geometry.

### Lighting, shadows, and reflections

Candidates:

`inconsistent light direction, conflicting shadows, detached shadows, missing contact shadows, unintended artificial glow, incoherent reflections, incorrect mirror content, inconsistent highlight direction`

Evaluate lighting against the described sources and materials. Multiple light sources may legitimately produce multiple shadows or highlights. Preserve requested soft lighting, flat lighting, bloom, neon, radiance, and emissive surfaces.

### Visible text and unwanted marks

Candidates:

`unintended text, unwanted watermark, unwanted signature, unwanted logo, misspelled lettering, duplicated lettering, malformed characters, illegible requested text, incorrect text placement`

When text is requested, target errors in its spelling, legibility, or placement. Do not use broad exclusions that suppress the requested lettering, signage, labels, logos, or typography.

### Video and shot continuity

Candidates:

`inconsistent motion, unintended jitter, temporal flicker, temporal warping, identity drift, facial drift, body-shape drift, unrequested wardrobe changes, unrequested prop changes, object popping, unexplained disappearing objects, duplicated moving elements, morphing anatomy, unstable background geometry, discontinuous contact, unintended foot sliding, inconsistent motion direction, flickering shadows, unstable reflections, abrupt unrequested scene changes, broken action continuity`

Prioritize failures relevant to the action and camera movement. Preserve intentional handheld motion, cuts, lighting changes, transformations, wardrobe changes, and objects entering or leaving the frame.

### Visible adult anatomical detail

Candidates:

`missing nipples, extra nipples, malformed nipples, distorted nipples, unnatural nipple texture, unnatural or inconsistent nipple coloration`

Use only when the corresponding adult anatomy is exposed, visible, and sufficiently resolved by the framing. Preserve natural pigmentation and asymmetry. Do not treat covered, cropped, or occluded anatomy as missing.

### Character-specific appearance exclusions

Conditional candidates:

`pubic hair, athletic physique, muscular build, fashion-model proportions, exaggerated curves, oversized head`

These describe appearance preferences rather than general rendering defects. Select them only when they conflict with an explicit requested appearance or an applicable character preset. For example, exclude muscular build only when the intended character is explicitly non-muscular.

Do not introduce these preferences when the requested appearance leaves them unspecified.

### Relevance check

Review the selected concepts against the completed positive prompt. Keep the most useful ones, remove contradictions and repetition, and ensure each remaining concept targets an unwanted result that could affect the requested scene.
