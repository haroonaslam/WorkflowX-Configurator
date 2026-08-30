# LTX 2.3 Common Rules and Guide

## Purpose and scope

Convert a short user idea plus duration into an LTX-2.3-ready video prompt. The output must be detailed enough to fill the requested duration, internally coherent, realistic in its motion, realistic in anatomical logic, and explicit about scene, subject, action, lighting, camera, and audio. Apply every relevant LTX-2.3 prompt-construction rule.

LTX-2.3 is especially responsive to specific prompt details. Write like a production shot description: describe what is visible, what changes over time, how the camera behaves, and what the viewer hears.

## Canonical Prompt Formula

Build every LTX prompt with this order unless the user's requested style demands otherwise:

```text
<pre-timing setup: capture style or shot type; subject with visible traits; specific environment; lighting, palette, textures, atmosphere; baseline audio.> <timed action progression: 0-3s, 4-6s, etc.; each range describes visible action, acting cues, camera movement, and sound changes.> <post-timing continuity: ending state, final held image or resolved motion, ongoing audio, camera/output constraints, and style rules that must remain true throughout.>
```

Do not output only a mood phrase. Convert mood into visible and audible details.

The timing blocks are not the whole prompt. They are the action sequence inside a larger prompt. Always surround them with pre-timing setup and post-timing continuity. Establish the shot, set the scene, describe the action, define the characters, identify camera movement, and describe audio.

## Timing Rules

Cover the entire requested duration with sequential ranges. Do not leave gaps.

Recommended beat counts:
- 3-4 seconds: 1-2 beats.
- 5-7 seconds: 2-3 beats.
- 8-10 seconds: 3-5 beats.
- 11-15 seconds: 4-6 beats.
- More than 15 seconds: use enough beats that each visible change has time to breathe.

Beat formatting:
- Use `0-3s:`, `4-6s:`, `7-10s:` style lines.
- Each beat should include visible action, camera behavior, and audio when relevant.
- The final beat should resolve the moment: a hold, reveal, reaction, ending gesture, line delivery, or clean pause.
- Use natural timing rather than mechanical choreography. The time ranges are for prompt structure, not exact frame control.
- If the user requests exact duration but no shot length, make the final beat end exactly on that duration.
- If dialogue is present, estimate spoken words conservatively. A 10 second clip supports a few short phrases, not a paragraph of speech.
- If the action is complex, simplify the sequence rather than compressing impossible motion into a short clip.

## LTX-2.3 Guide Principles

Always apply these principles:
- Specific beats outperform vague concepts. Replace generic action with concrete subject, location, motion, and sensory detail.
- Prompt coverage should scale with duration so longer clips have enough described action to prevent rushed or invented filler.
- Describe the full scene: subject, action, environment, lighting, camera behavior, and audio.
- Use production language when appropriate: shot scale, lens feel, camera motion, lighting style, palette, texture, atmosphere, pacing.
- Use present tense action verbs.
- Express emotions through visible behavior. Prefer physical cues, facial movement, posture, gaze, pauses, breath, or hand movement over abstract labels.
- For dialogue, use short quoted phrases separated by acting direction. Long uninterrupted monologues are less reliable.
- Audio matters. Include room tone, ambience, music, voice quality, footsteps, fabric movement, object sounds, crowd noise, weather, or singing when relevant.
- Facial expression, timing, pauses, and emotional beats should be directed explicitly when they matter.
- Camera movement should include both the movement and its result, such as what becomes visible after a pan or how the face fills the frame after a push-in.
- Keep prompt language natural. Avoid mathematical camera instructions, frame counts, exact angles, or other over-constrained specifications.

## LTX-2.3 Responsiveness Rules

Because LTX-2.3 follows detailed text more closely than earlier versions:
- Use exact but natural acting direction: pauses, glances, changed voice, interrupted movement, small hesitation, held eye contact.
- Describe voice qualities where speech matters: calm, strained, amused, whispering, resonant, distorted, robotic, singing, cracking, breathy, casual.
- For emotional scenes, create a visible acting path. Example pattern: looks down -> pauses -> inhales -> looks back -> speaks in a changed voice.
- For longer clips, add multiple sequential beats rather than asking one sentence to stretch.
- For dialogue scenes, alternate speech and physical behavior so timing is clear.

## Shared build sequence

2. Identify style:
   - If the user asks for cinematic, use film language.
   - If the user asks for vlog, phone, documentary, surveillance, webcam, raw, or unedited, avoid over-cinematic wording. Use handheld, practical light, natural audio, casual framing, autofocus shifts, small exposure changes, ordinary background detail, and no staged composition.
   - If the user asks for animation, stylized, painterly, noir, analog film, or fashion editorial, use matching style markers.

3. Expand the scene:
   - Subject: age as adult where relevant, appearance, wardrobe or lack of wardrobe when allowed, posture, expression, distinguishing features.
   - Action: the main action as a realistic sequence with cause and effect.
   - Environment: location, time of day, weather, props, surfaces, background activity.
   - Lighting: natural sunlight, practical lamps, neon, candlelight, backlight, rim light, flicker, high contrast, soft shade, overcast, etc.
   - Color and texture: muted, vibrant, glossy, rough, wet, dusty, worn fabric, smooth metal, skin texture, haze, smoke, particles.
   - Camera: static, handheld, tracking, slow push-in, pan, tilt, orbit, over-the-shoulder, low angle, overhead, close-up, medium, wide, macro, shallow depth of field.
   - Audio: ambient sound, music, speech, vocal quality, volume, room tone, weather, object handling, footsteps, crowd, mechanical noise.
   - Scale: intimate, claustrophobic, expansive, epic, close and private, public and busy.
   - Temporal effect when requested: continuous take, lingering shot, slow motion, time-lapse, rapid cuts, freeze-frame, fade-in, fade-out, seamless transition, sudden stop.
   - Visual effects when requested: particle systems, motion blur, depth of field, lens flare, analog film grain, pixelated edges, jittery stop-motion.

4. Create an internal timeline scaffold:
   - Assign each beat one dominant action.
   - Include micro-actions for acting: glance, blink, pause, breath, hand movement, turn, lean, smile, tightened grip, shifting weight.
   - Keep physics simple and plausible.
   - Do not overload a beat with too many simultaneous actions.
   - Keep this scaffold internal unless the user explicitly asks to see planning.

5. Write the final integrated LTX prompt:
   - Use one cohesive integrated prompt unless the user asks for a planning breakdown.
   - Embed the timed ranges directly into the final prompt.
   - Put pre-timing setup before the first timestamp: capture style, subject, character definition, environment, lighting, palette, texture, atmosphere, and baseline audio.
   - Put post-timing guidance after the last timestamp: ending state, sustained style/capture constraints, audio continuity, and camera/output continuity.
   - Preserve the trigger words, LoRA names, character names, wardrobe constraints, and duration.
   - Make the prompt flow in the same order as the internal timeline scaffold.
   - Include dialogue in quotation marks when spoken words are requested.
   - Add acting direction between dialogue fragments.
   - Keep the final prompt coherent with the selected style.
   - Each timed range should be written as finished prompt prose, not shorthand notes.

6. Add a negative prompt:
   - Include general artifacts.
   - Add style-specific negatives when useful.

## Required Elements Checklist

Every strong prompt should include:
- Shot establishment: what kind of shot or capture style starts the clip.
- Scene setting: location, light, color, texture, atmosphere.
- Action: what happens from beginning to end.
- Character definition: visible age category, appearance, clothing, posture, expression, physical cues.
- Camera movement: how the frame moves or stays still, and how the subject appears after movement.
- Audio: ambience, voice, music, object sounds, weather, or silence.

Adjust detail by shot scale:
- Close-up: include facial movement, eyes, mouth, skin texture, breath, subtle hand movement, shallow focus.
- Medium shot: include body posture, arm movement, props, nearby environment, camera height.
- Wide shot: include spatial layout, background movement, weather, lighting zones, crowd or landscape.

Shot establishment examples to adapt:
- Live broadcast: reporter, microphone, background activity, camera pan, ambient crowd or machinery.
- Vlog/raw phone video: handheld arm-length framing, small shake, practical light, phone mic, ordinary room noise, casual pauses.
- Documentary: observational camera, natural light, unpolished sound, real location details, restrained camera movement.
- Fashion/editorial: deliberate pose, stylized wardrobe, controlled lighting, slow camera, texture and color emphasis.
- Animation: state the animation medium and motion style early, such as claymation, hand-drawn, stop-motion, 3D animation, pixel art.

Scene-setting detail must include at least three of these:
- Lighting condition.
- Color palette.
- Surface texture.
- Weather or atmosphere.
- Background activity.
- Props or set dressing.
- Time of day.

## Dialogue Rules

For speaking characters:
- Split speech into short phrases.
- Put spoken words in quotation marks.
- Insert acting cues between lines.
- Describe voice quality: whispering, casual, breathy, amused, strained, resonant, radio-like, robotic, singing, etc.
- Include language or accent only when requested or relevant.
- Match speech length to duration. A 5 second clip cannot contain a long monologue.
- Avoid uninterrupted speech blocks. Use a gesture, look, breath, pause, or camera move between lines.
- If the user gives a long line, shorten it into a few natural fragments while preserving intent.
- Describe the acoustic context of the voice: crisp studio mic, phone mic, echoing hallway, muffled through a door, distant crowd, quiet room tone.

Example structure:

```text
0-3s: The character looks into the handheld camera and begins with a short line, then pauses and smiles.
4-7s: They glance away, adjust their posture, and continue with a second short phrase.
8-10s: They lower their voice, finish the thought, and hold eye contact as room tone continues.
```

## Audio Rules

Use audio whenever it helps the clip feel grounded:
- Ambience: refrigerator hum, rain, traffic, insects, crowd murmur, room tone, wind, cafe noise.
- Voice: clean dialogue, faint breath, whisper, shout, laughter, singing, accent, language.
- Object sounds: glass on counter, fabric rustle, footsteps, door hinge, chair scrape, camera handling noise.
- Music: soft ambient bed, pulsing club bass, old radio, orchestral swell, no music.
- Volume: whisper, mutter, normal conversational voice, shout, scream, distant, muffled, close to microphone.
- Voice style: energetic announcer, calm narrator, resonant voice with gravity, distorted radio voice, robotic monotone, casual vlog speech, breathy aside.

For realistic vlog or raw footage, prefer practical audio: phone mic, room tone, background appliances, small handling noise, uneven volume, casual pauses.

## What Works Well

Lean into:
- Clear compositions: wide, medium, and close-up shots with readable subject placement.
- Natural motion: walking, turning, leaning, breathing, speaking, looking, touching props, small gestures.
- Emotive human moments: subtle facial shifts, pauses, glances, swallowed words, tightened fingers, uneven breath.
- Atmosphere: fog, mist, rain, reflections, dust, smoke, particles, golden hour, neon spill, warm practical lamps.
- Clear camera language: handheld follow, slow push-in, pan, tilt, static frame, over-the-shoulder, low angle, overhead.
- Stylized looks when requested: noir, analog film, fashion editorial, painterly, comic-book, claymation, pixel art, documentary, raw vlog.
- Lighting control: rim light, backlight, flicker, candlelight, soft window light, high contrast, muted palette.
- Voice and singing: short, paced lines with acting cues.
- Single-subject performances with clear facial nuance.
- Environments with readable ambience: cafe, forest, rainy street, studio, small kitchen, live broadcast, workshop, club, hotel room.
- A camera move with a purpose: reveal a background event, tighten on an expression, follow a subject, or reframe after a gesture.

## What To Avoid

Avoid:
- Vague prompts with no subject, setting, or action.
- Internal labels without visible cues, such as only saying "sad" or "confused."
- Readable text, signage, logos, or precise typography requirements.
- Overly complex physics or chaotic motion.
- Too many people, too many actions, or too many visual priorities in one short clip.
- Contradictory lighting or impossible camera direction.
- Exact numerical choreography beyond the integrated timed ranges.
- Insufficiently described action for the requested duration.
- Overcomplicated prompts with competing styles.
- Mixed capture modes unless intentional. Do not call something "unedited vlog" and then add dolly, crane, anamorphic, studio lighting, and cinematic color grading.
- Describing an emotion without performance direction. Convert emotion into face, breath, voice, gaze, posture, and timing.

Repair rules:
- If too vague, add subject, place, action, lighting, camera, and sound.
- If over-constrained, convert exact numbers into natural language.
- If the described action does not adequately cover the duration, add beats.
- If conflicting, choose the stronger user intent and remove the contradiction.
- If a prompt demands readable text or logo accuracy, replace it with non-readable signage, symbolic graphics, or broad design cues.
- If physics are too complex, reduce the number of moving objects and make one motion dominant.
- If a scene is overloaded, choose one focal subject, one main action, and one background detail.

## Common Mistake Repairs

Use these transformations:
- Too vague: replace "nice nature video" with a specific place, weather, subject, time of day, camera movement, and sound.
- Over-constrained: replace exact counts, degrees, and per-second movement with natural phrasing such as "a few birds drift across the frame as the camera slowly pans."
- Duration mismatch: if the clip lacks adequate action coverage, add beginning, middle, and end beats with concrete motion.
- Conflicting directions: remove one side of the contradiction, such as "still lake" vs "crashing waves."
- Internal emotion: replace "she is sad" with "she looks down, blinks slowly, swallows, and speaks with a quiet uneven voice."
- Unclear camera: replace "cool camera movement" with "the handheld camera follows from behind, then slowly pushes in until her face fills the frame."

## Compact construction patterns

Use these structures without copying their wording:
- Live event reveal: start with a reporter or host in a defined location, include ambient activity, deliver short dialogue, pan or reframe to reveal the event, then end on the reaction and sound.
- Comedic group scene: establish calm routine, introduce one small disruptive action, pause for reaction, deliver a short punchline, then hold on the guilty or embarrassed subject.
- Emotional monologue: open close on a face, give one short phrase, pause and look away, continue with a changed expression or voice, then push in for the final line.
- Raw vlog: begin in a casual real-world setting, use handheld framing and ordinary audio, let the speaker talk in short natural phrases, include small self-adjustments and pauses, end with an unpolished hold.

## Vocabulary Bank

Use these as needed, not all at once.

Categories:
- Animation: stop-motion, 2D animation, 3D animation, claymation, hand-drawn.
- Stylized: comic-book, cyberpunk, 8-bit pixel art, surreal, minimalist, painterly, illustrated.
- Cinematic: period drama, film noir, fantasy, epic space opera, thriller, modern romance, experimental, arthouse, documentary.
- Realistic capture: unedited vlog, phone video, webcam, documentary handheld, raw behind-the-scenes, natural home video.

Visual details:
- Lighting: flickering candles, neon glow, natural sunlight, overcast daylight, warm practical lamps, dramatic shadows, soft window light.
- Textures: rough stone, smooth metal, worn fabric, glossy counters, rain-streaked glass, damp pavement, skin texture, dusty air.
- Palette: vibrant, muted, monochrome, high contrast, warm, cool, natural, desaturated.
- Atmosphere: fog, rain, dust, smoke, steam, particles, reflections, haze.

Camera language:
- follows, tracks, pans across, circles around, tilts upward, pushes in, pulls back, overhead view, handheld movement, over-the-shoulder, wide establishing shot, static frame, close-up, medium shot, macro lens feel, shallow focus.

Film and capture characteristics:
- film grain, lens flare, soft autofocus shift, phone mic audio, handheld shake, exposure breathing, motion blur, depth of field, raw unedited take, continuous shot.

Pacing:
- slow motion, time-lapse, rapid cuts, lingering shot, continuous take, sudden stop, fade-in, fade-out, seamless transition, held pause.

## Final Quality Gate

Before finalizing, verify:
- The integrated timed ranges cover the exact duration without gaps.
- The prompt has pre-timing setup before the first timestamp.
- The prompt has post-timing continuity/output guidance after the final timestamp.
- The output respects requested style, including non-cinematic/raw styles.
- The LTX prompt has subject, action, environment, lighting, camera, and audio.
- Longer clips have enough beats to avoid rushed action.
- Dialogue is short and broken up with acting direction.
- Emotion is shown through physical cues.
- The prompt avoids readable text/logos unless unavoidable.
- Adult prompts include all user requirements addressed.
- There are no contradictions in lighting, motion, camera, consent, or character behavior.
