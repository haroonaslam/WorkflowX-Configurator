# WorkflowX AuK audio

Find these nodes under **WorkflowX â†’ Audio â†’ AuK**. Node titles end in **X**; IDs use `WorkflowXAuK`. This is the customized WorkflowX version, separate from upstream AuK. All controls and script syntax below are unchanged.

# Chained voice cloning

Connect the AuK model, encoder, VAE, and one reference recording to **AuK Chained Clone**. Open the included BF16 example and select a recording in **Load Audio**. Connect audio to **Preview Audio** or **Save Audio (Advanced)**, and segment_report to **Preview as Text**.

```text
[Shy][c-whisper] Hello there. (3s)
[Happy][c-laugh][c-volume:-6db] That is interesting. (2.5s)
[c-speed:0.8][c-pitch:+3.5] Let me explain.
```

Each nonblank line starts with **one optional voice style**, followed by any audio changes in the order you want. The selected original recording supplies the voice for each line; with Multi-speaker off, this is always Voice 1. Each change works on the result of the previous change on that line; the finished lines are then joined together.

## Controls

Style instructions put the delivery first: `[Happy] Hello there, how are you?` becomes `Say the following in a happy tone using the same voice: "Hello there, how are you?".` Conversion instructions follow the task guide directly; for example, `[c-emotion:quietly disappointed]` becomes `Change the emotion to quietly disappointed.`

Place the cursor on a line. **Voice style** opens searchable choices and replaces the line's current style. **Add conversion** adds an audio change. Numbered chips show the order and current values; click a chip to edit, move earlier/later, or remove it. Hover or focus a control for help; Escape dismisses menus and help. The script remains editable, including custom styles such as `[wistful]`, and text undo remains available. A connected script must be edited in its source text node.

Speed, volume, and pitch have labeled value fields. Type any finite decimal; the +/− buttons offer convenient increments of 0.05×, 0.5 dB, and 0.5 semitones. Defaults are 1×, 0 dB, and 0 semitones, which leave the audio unchanged. Speed must be greater than zero. Volume accepts an optional `db` suffix, in either case. Positive volume is louder, negative is quieter; positive pitch is higher, negative is lower.

## Audio changes

| Category | Tags |
| --- | --- |
| Voice | `c-whisper`, `c-normal`, `c-emotion:description`, `c-timbre:description`, `c-deaccent` |
| Sounds | `c-laugh`, `c-chuckle`, `c-cough`, `c-sneeze`, `c-sigh`, `c-gasp`, `c-clears throat`, `c-breath`, `c-humming` |
| Removal | `c-remove:sound` |
| Acoustics | `c-speed:factor`, `c-volume:decibels`, `c-pitch:semitones` |
| Cleanup | `c-enhance`, `c-denoise`, `c-dereverb`, `c-repair:defect` |

All tags belong at the start of the line and are case-insensitive. Unknown voice styles are allowed; unknown conversions are rejected. `[laughs]` is a voice style for speaking while laughing, whereas `[c-laugh]` asks for an added laugh before the words. `[whispers]` asks for whispered delivery when the line is first spoken; `[c-whisper]` converts the resulting audio to a whisper. Content/lyric editing and separation remain in the existing nodes.

If an older script has several ordinary styles, choose one and use conversions for additional changes. For example, change `[Shy][whispers]` to `[Shy][c-whisper]`. The node reports the source line that needs correcting; it does not silently rewrite saved scripts.

## Length and sound

A trailing `(2.5s)` sets the original spoken line's length. Otherwise, length is the spoken-word count divided by **words_per_second**, default 2. Contractions and hyphenated words count as one. Tags and timing do not count; interior parentheses stay in the dialogue. Languages without word spaces may need explicit lengths.

Speed adjusts the original cloning duration using the base duration times Speed timing multiplier divided by the factor; there is no speed-edit pass. Each added sound starts at the beginning and gets **sound_extra_seconds**, default 0.5 seconds. Other changes retain the current length. Several added sounds are each requested at the beginning of the current clip, so their final audible order can differ from the tag order. **gap_seconds**, default 0, adds silence only between finished lines. Audio is mono 24 kHz, joined without normalization, crossfades, or trimming.

The report lists each instruction, parameter, seed, requested and actual length, plus the finished line's start/end times. Initial seeds are base seed + line index (starting at zero); changes add their one-based position, including unchanged choices. Seeds wrap at 2^64. Choose **fixed** to keep random choices repeatable. Existing Base/Flash settings and loaders are retained. The extra sound control is appended, preserving older widget positions and output sockets.

These are requested performances and audio edits. Voice continuity, word preservation, style adherence, and exact dB or pitch changes can vary; listen to the result. Instructions use the extension's [task guide](https://github.com/Saganaki22/ComfyUI-AuK/blob/main/docs/GUIDE.md), with local whisper preparation and no language-model prompt enhancement.

The complete script is checked before generation. Cancellation or errors identify the segment and change and never return an incomplete recording as success.

## Checks

Run `python -m unittest discover -s tests -p "test*.py" -v` with ComfyUI's Python, and `node tests/test_tag_insertion.mjs` for script-edit checks. Refresh the browser after updating; the server must reload the Python node once.


## Two speakers

Enable **Multi-speaker**, connect recordings to **Voice 1** and **Voice 2**, and put `@voice1` or `@voice2` before the line's tags:

```text
@voice1 [Happy] Hello there. (2s)
@voice2 [Shy][c-whisper] Nice to meet you. (3s)
This line continues with voice 2.
@voice1 [c-laugh] Likewise! (2s)
```

An unmarked line continues the preceding speaker. Before any speaker is selected, Voice 1 is used. Blank lines do not change the speaker. Prefixes are case-insensitive and never become spoken words or instructions. The second recording is required only if a line uses Voice 2.

The **Speaker** menu changes the current line's prefix. **Continue previous** removes it. The summary shows the resolved voice and marks inherited choices. Style and conversion edits preserve the prefix, and connected scripts are edited in their source text node.

Turn Multi-speaker off to use Voice 1 for every line; prefixes stay in the script for later use but are not spoken. Both audio sockets stay visible. Each line starts from the chosen speaker's original recording, then applies its audio changes in order. Reports identify the selected voice. Use `example_workflows/05_two_speaker_clone.json` for the BF16 example and choose your own recordings.

## Inline edits and Segment editor

Two independent switches are off by default. Existing scripts and whole-line generation keep their previous behavior.

Enable **Inline edits** to change selected words:

```text
@voice1 [Happy][c-laugh] Hello, how are you <breath>i am so tired</breath> but <sad>i am still here!</sad> (6s)
@voice2 [Calm] Please <whisper>keep this between us</whisper>. (4s)
```

Select words and open **Inline edit** to wrap them. Place the cursor inside a span to change its effect, edit a value, or remove its markers. Spans cannot overlap or nest. Keep them within one line and include spoken words.

Use ordinary styles such as `<sad>words</sad>`, aliases such as `<whisper>words</whisper>` or `<breath>words</breath>`, or explicit conversions such as `<c-speed:1.25>words</c-speed>`. Parameterized closing tags omit the value. All catalog styles and conversions are available. A breath or laugh adds a sound before those words; breathy delivery or speaking while laughing changes how those words sound.

Each piece first uses the line's main voice style and selected original recording. Only marked pieces receive the inline edit. The pieces are joined, then the line's leading c-tags apply once to the whole line. A main whisper conversion therefore affects the entire line, even if a span was edited differently.

An explicit duration is shared among pieces by word count. Otherwise each piece uses the words-per-second setting. Added sounds receive extra sound time, and speed changes alter the affected piece's length. There are no inserted gaps within a line. Short pieces may sound less natural at joins; phrase-sized selections work best.

With **Inline edits off**, tag-shaped inline markers are removed, their words remain, and the line is generated without splitting. Unknown inline effect names or values are ignored in this mode. Ordinary comparisons such as `less than < 3` remain text.

### Segment editor

Enable **Segment editor**, then use the normal **Run** button. Every line generates continuously; completed lines become playable as they finish. The combined recording automatically reaches Preview/Save Audio after the entire batch succeeds.

- **Previous / Next:** browse retained lines, including while generation runs. The displayed words, voice, seed, and duration describe the retained take.
- **Regenerate:** replace only the selected line using its current script text, tags, recordings, and settings with a fresh seed. It regenerates the entire line, including its inline edits and conversions. A failed replacement keeps the previous audio.
- **Add line…:** enter exactly one nonblank script line. **Add & generate** inserts it after the selected line. With a local script, the text is inserted into the textbox and saved with the workflow; normal text undo remains available. With a connected text input, the addition is marked **Editor-only** and the source node stays unchanged.
- **Finalize:** send a revised recording downstream, assembled from the retained takes with the current Gap. It does not regenerate speech or run upstream model/text-generation nodes. Takes may intentionally have different voices or settings.
- **Clear editor:** remove this node's temporary takes. Saved output recordings are untouched.

Regeneration and additions do not send a revised recording downstream until Finalize. Mutating actions are unavailable while a job is active. An added line whose generation fails remains as an ungenerated slot for retry; all slots need audio before Finalize.

Edit ordinary lines in the local script or connected source node. Regenerate reads current source text. Inserted lines participate in speaker inheritance for subsequent regeneration; existing takes keep their recorded voices. Other script/settings changes do not invalidate retained audio. If manual edits change the source's nonblank line count, start a fresh full Run before regenerating or adding; retained audio can still be played or finalized.

Every normal Run clears this node's previous editor cache. Temporary takes also disappear on Clear editor, switching the editor off, server restart, or 24 hours of inactivity. Refresh can reconnect to a live session. Each line retains one lossless audio file and one playback file; successful replacement deletes the old pair. There is no previous-take or intermediate-piece history. Initial batch failure/cancellation keeps completed previews for inspection but never sends incomplete audio as a successful result.

Use `example_workflows/06_inline_review_clone.json` with the installed BF16 models and your recordings. The saved switch is still named `review_each_line` for compatibility; its visible label is Segment editor. Internal queue helpers are not nodes you need to add.


### Starting style and audio edits

Voice style sets the initial cloning tone, for example `[Happy]`. Both edit menus now insert explicit c-tags: choosing Excited inserts `[c-emotion:excited]` for a whole line or `<c-emotion:excited>words</c-emotion>` inline. Inline edits clone the pieces, edit marked pieces, and join them; leading c-tags then edit the whole assembled line.

Delivery edits use `c-delivery:description`, for example `<c-delivery:speaking while laughing>That was unexpected.</c-delivery>`. This changes the speech delivery; `c-laugh` instead adds a laugh before the words. `c-whisper` retains its dedicated whisper behavior. Parameterized closing tags contain only the operation name. Old shorthand such as `<excited>` remains supported for saved scripts; new picker choices and generated scripts use c-tags.


### Speed tags control cloning time

`c-speed` now changes the original speech duration; it does not send generated audio through a speed-edit pass. The base is the explicit line duration or word-count estimate. Adjusted time is base × Speed timing multiplier ÷ speed factor. The new control defaults to 1.0; increase it for more room. It affects only pieces with non-neutral speed tags.

Leading speed applies to all pieces; inline speed applies to its own piece. Applicable factors multiply, and the timing multiplier applies once. Factor 1 alone remains unchanged. Added sounds receive Extra sound time after cloning and are not compressed by speed. The relative placement of speed and sound tags no longer changes timing. Other audio edits keep their order and seeds. Changing the timing multiplier affects the next generation; retained editor takes remain unchanged until regenerated.


### Saved custom choices

Open a picker and choose **Save custom choice…**. Select a category and supported effect, enter its value when needed, and give it a name. The choice appears in that category and inserts with one click. Edit choices are shared by Add conversion and Inline edit; starting styles are saved separately in Voice style. Use **Manage saved…** to edit or delete choices. Choices are stored with this node in the workflow, so save the workflow to keep and share them. Removing a saved choice does not remove tags already written in the script.
