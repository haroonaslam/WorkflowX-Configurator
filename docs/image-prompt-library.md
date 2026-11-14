# Image Prompt Library

Double-click **Launch Image Prompt Library.cmd** in the WorkflowX folder. This opens a local browser app and works with ComfyUI closed. It uses the portable ComfyUI Python when available, then the repository virtual environment, then Python on PATH. The standalone dependency is Pillow; ComfyUI already supplies it.

After restarting ComfyUI normally and refreshing the page, **XPrompts → Open image prompt library** opens the same app and database. Existing saved XPrompts are unchanged. The integration is intended for a browser on the same computer as ComfyUI.

Choose a PNG, JPEG, WebP, or folder with **Browse**, or paste its local path. Subfolders are included by default. **Scan images** indexes embedded ComfyUI metadata and creates thumbnails without changing or copying originals. Repeated scans skip unchanged images. **Cancel scan** retains completed records. **Stop app** stops the local server; closing the tab alone leaves it available for reopening.

The library groups by full positive text, preserving case, punctuation, and internal spacing. Only outer whitespace and line endings are normalized. Negative prompts and settings remain attached to individual images. Search matches prompts and filenames; **Copy** copies the positive text. **View all images** opens the group gallery, with extraction details and source-folder rescanning. Clicking an image opens its original at full size.

## Extraction

The extractor follows the embedded execution graph from supported image outputs to sampler/guider conditioning. It supports core CLIP encoders (including SDXL and Flux), native StringConcatenate, KJNodes JoinStrings/JoinStringMulti, literal text, reroutes, materialized WorkflowX relay values, KJNodes boolean switches, ControlNet conditioning paths, and common conditioning transforms.

Text joins preserve their separators and input order. ConditioningCombine retains separate branches; ConditioningConcat follows ComfyUI's first-source-branch semantics. Copyable text flattens conditioning branches with newlines; it is not a substitute for their conditioning operations, which remain in the extraction details.

Unknown custom nodes, missing runtime outputs, cycles, ambiguous image outputs, differing multi-stage prompts, and visual-workflow-only metadata go to **Needs review**. Review shows recovered text and node diagnostics; saving a corrected full prompt moves that image into its matching group while preserving extraction evidence. No workflow or custom-node Python is executed. Files without embedded metadata cannot have their prompts recovered automatically. Sidecar files and non-ComfyUI metadata are not scanned.

## Storage and development

The SQLite index, cached thumbnails, server state, and local log live in `%LOCALAPPDATA%\WorkflowX\ImagePromptLibrary` on Windows. Moving/deleting originals marks them unavailable in the gallery without deleting their prompt records. Changing an image invalidates its prior extraction and manual correction on rescan.

The server binds only to `127.0.0.1`, requires a per-session token for library/filesystem APIs, checks local origins, and serves images by indexed IDs. It makes no external requests. Both launch paths reuse a single server per library directory.

For an isolated test library:

```powershell
python image_prompt_library/launch.py --home C:\Temp\WorkflowX-Prompt-Test
```

The resolver's supported node layouts are explicit in `image_prompt_library/extractor.py`; add adapters and metadata fixtures together when supporting another custom node. Run `tests/test_image_prompt_library.py` with pytest. If the parent ComfyUI package's eager imports interfere with isolated tests, copy this test module to an external temporary directory and run pytest there with the repository on Python's import path.
