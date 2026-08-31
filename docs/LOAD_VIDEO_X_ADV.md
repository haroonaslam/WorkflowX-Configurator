# Load VideoX Adv

`Load VideoX Adv` loads, visually trims, crops, and resizes a ComfyUI input video. It is registered as `WorkflowX_LoadVideoXAdv` under `WorkflowX/Video`.

## Visual workflow

Select or upload a video, enable **Crop**, then draw one normalized crop rectangle directly over ComfyUI's native video player. A transparent canvas supplies dimming, outline, and resize handles without creating a second player. Clicking the video picture is reserved for crop interaction; playback starts from the native play control. The remaining native volume, seek, fullscreen, and overflow controls stay available. Crop snapping, output snapping, resize modes, anchors, resampling, upscaling, and solid RGB padding follow `Load ImageX Adv`. The crop is applied to every selected frame. Selecting a different source resets trim and crop rectangles but retains the remaining geometry preferences.

Open **Timeline** for the floating player and bounded thumbnail filmstrip. Its large in/out handles resize the selection, dragging the highlighted body slides the whole range, and a separate scrubber moves the playhead. The selection duration is editable in seconds when the `seconds` input is unconnected and becomes a read-only wired value when connected. The window follows the graph, shares its node's canvas layer order, and supports stable pointer-captured dragging, eight-way resizing, position/size locking, minimize, fullscreen, and per-node geometry persistence.

When `seconds` is unconnected, the in/out handles move independently. When it is connected, they maintain the wired duration and slide the range. A selection that reaches the end of a short source simply returns the available media. Average FPS supplies visual frame snapping and frame readouts; backend slicing uses the corresponding timestamp window.

## Outputs and processing

Outputs are ordered as `video` (`VIDEO`), `video_frames` (`IMAGE`), `audio` (`AUDIO`), `width` (`INT`), and `height` (`INT`). Unconnected media outputs return `None`.

The queued prompt carries a transient connection mask, verified against ComfyUI's dynamic prompt at execution. This keeps the saved workflow clean and selects the least expensive path:

- Width/height-only consumers probe metadata without decoding media.
- A native-video-only trim with no spatial transform returns a lazy `VideoFromFile` trim.
- Audio-only consumers decode only audio.
- Frame consumers and spatial transforms decode frames once; rebuilt native video and frame outputs share that batch.

Source paths are constrained to ComfyUI's input directory and filtered to recognized video media. Phone-video rotation is included in metadata and decoding so crop coordinates match the displayed orientation. Rebuilt video retains source average FPS, bit depth, color space, trimmed audio, and frame/audio alignment.
