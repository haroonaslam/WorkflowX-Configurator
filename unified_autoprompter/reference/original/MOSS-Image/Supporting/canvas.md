# MOSS canvas resolution

These rules define the layout prompt's coordinate canvas, not adapter or generation settings. For I2I, establish the intended output canvas from the supplied image, user dimensions, or confirmed existing layout before using the cases below. If its size is essential and unavailable, ask for it; do not assume that an unseen source is 1024 square. The no-size default below is for T2I only. An explicit requested resize or crop overrides the original size and requires box updates.

Resolve the canvas before creating any items. Width W and height H must be finite positive integers, each divisible by 16. An explicit exact size is a requirement to validate, not permission to silently round it.

Apply these cases:
1. **Both dimensions supplied:** use them if valid. If a ratio is also supplied, verify W/H matches it; for a reduced ratio a:b use W*b = H*a. If exact dimensions and exact ratio disagree, ask which requirement controls.
2. **One dimension and a ratio supplied:** derive the other side exactly: H = W*b/a or W = H*a/b. Validate both resulting dimensions. Example: width 1536 and ratio 3:2 gives height 1024.
3. **One dimension without a ratio:** ask for the missing dimension or ratio. Do not assume a square or ignore the supplied side.
4. **Ratio only:** require finite positive ratio terms. Convert a finite decimal ratio into reduced positive integers a:b. Set W = 16*k*a and H = 16*k*b. Choose the positive integer k whose pixel count 256*k*k*a*b is closest to 1,048,576, breaking ties toward the smaller k. Checking the floor and ceiling of sqrt(1048576/(256*a*b)), with a minimum k of 1, suffices. This preserves the exact ratio and alignment rather than independently rounding both sides. Example: 16:9 selects 1280 by 720.
5. **No size or ratio:** resolve to 1024 by 1024.
6. **Invalid or conflicting inputs:** ask one concise question before outputting a layout. Examples include zero, negative, non-finite, non-integer or unaligned dimensions; an invalid ratio; or a derived side that is not aligned. Offer a sensible valid size if useful, but do not treat it as accepted. Exact 1001 by 777 is invalid; do not silently substitute 1008 by 784.

A current user correction overrides the corresponding earlier size choice. Never combine width from one version with height from another unintentionally. Treat unusually large ratio-derived sizes as a reason to confirm a practical canvas rather than claiming compatibility with an unknown renderer.

Track whether either dimension was inferred. Apply the canvas communication branch in the selected output contract; keep the chosen size outside the model caption. Once resolved and, when required, confirmed, use the same W and H for every coordinate conversion.
