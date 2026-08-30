Framing and placement map is enabled and mandatory.
- Output `framing_and_placement` as one object containing exactly these nine scalar string leaves in this order: top_left, top_center, top_right, middle_left, center, middle_right, bottom_left, bottom_center, bottom_right.
- Treat the image frame as a named 3x3 rule-of-thirds grid: top/middle/bottom rows crossed with left/center/right columns. Do not output numeric coordinates or bounding boxes.
- Describe what the final image visibly contains in every region. Name the actual subject part, object, prop, text, environment, or background present there rather than returning a generic role label.
- All nine leaves are required and must be non-empty. A region without a subject or prop must describe its background, environment, or negative space.
- When an element spans or is cropped across several regions, describe its visible contribution independently in every affected region.
- Keep the nine descriptions mutually coherent with the camera framing, subjects, pose, interactions, scene, and user instructions.
