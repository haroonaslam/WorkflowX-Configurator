const MODES = Object.freeze({
  ideogram4: Object.freeze({ label: "Ideogram 4", order: "yx", orderLabel: "ymin, xmin, ymax, xmax", palette: true, coordinateSpace: "grid" }),
  krea2: Object.freeze({ label: "Krea2", order: "xy", orderLabel: "xmin, ymin, xmax, ymax", palette: true, coordinateSpace: "grid" }),
  moss_image: Object.freeze({ label: "MOSS-Image", order: "yx", orderLabel: "ymin, xmin, ymax, xmax", palette: false, coordinateSpace: "centered_pixels" }),
});

export const BBOX_MODE_OPTIONS = Object.freeze([
  ["", "None"],
  ["ideogram4", "Ideogram 4 compatible"],
  ["krea2", "Krea2 compatible"],
  ["moss_image", "MOSS-Image compatible"],
]);

export function bboxModeConfig(mode) {
  return MODES[String(mode || "")] || null;
}

export function unwrapBBoxPayload(payload) {
  if (!payload || typeof payload !== "object") return {};
  return payload.prompt_json && typeof payload.prompt_json === "object" ? payload.prompt_json : payload;
}

export function hasBBoxPayload(mode, payload) {
  const source = unwrapBBoxPayload(payload);
  if (mode === "moss_image") {
    return Boolean(source?.summary?.caption || (Array.isArray(source?.items) && source.items.length));
  }
  const decomp = source?.compositional_deconstruction || {};
  return Boolean(source?.high_level_description || decomp.background || (Array.isArray(decomp.elements) && decomp.elements.length) || (Array.isArray(source?.elements) && source.elements.length));
}

function clamp01(value) {
  return Math.max(0, Math.min(1, Number(value) || 0));
}

function orderedEdges(mode, bbox, width, height) {
  const config = bboxModeConfig(mode) || MODES.ideogram4;
  let xmin;
  let ymin;
  let xmax;
  let ymax;
  if (config.order === "xy") [xmin, ymin, xmax, ymax] = bbox;
  else [ymin, xmin, ymax, xmax] = bbox;
  if (config.coordinateSpace === "centered_pixels") {
    xmin = Number(xmin) + width / 2;
    xmax = Number(xmax) + width / 2;
    ymin = Number(ymin) + height / 2;
    ymax = Number(ymax) + height / 2;
    return [xmin / width, ymin / height, xmax / width, ymax / height];
  }
  return [Number(xmin) / 1000, Number(ymin) / 1000, Number(xmax) / 1000, Number(ymax) / 1000];
}

export function nativeBoxToNeutral(mode, element, index = 0, width = 1024, height = 1024) {
  const fallback = [80 + index * 40, 80 + index * 40, 320 + index * 40, 360 + index * 40];
  const [rawXmin, rawYmin, rawXmax, rawYmax] = orderedEdges(mode, Array.isArray(element?.bbox) ? element.bbox : fallback, width, height);
  const xmin = clamp01(rawXmin);
  const ymin = clamp01(rawYmin);
  const xmax = clamp01(rawXmax);
  const ymax = clamp01(rawYmax);
  const label = typeof element?.label === "string" ? element.label : element?.label?.name || element?.label?.type || "";
  const palette = Array.isArray(element?.color_palette) ? element.color_palette.map((item) => String(item || "").trim()).filter(Boolean) : [];
  return {
    type: element?.type === "text" || label === "text" || Boolean(element?.text) ? "text" : "obj",
    text: String(element?.text || ""),
    desc: String(element?.caption || element?.desc || element?.description || ""),
    palette,
    x: Math.min(xmin, xmax),
    y: Math.min(ymin, ymax),
    w: Math.max(0.04, Math.abs(xmax - xmin)),
    h: Math.max(0.04, Math.abs(ymax - ymin)),
  };
}

export function neutralBoxToNativeBbox(mode, box, width = 1024, height = 1024) {
  const config = bboxModeConfig(mode) || MODES.ideogram4;
  let xmin = box.x;
  let ymin = box.y;
  let xmax = box.x + box.w;
  let ymax = box.y + box.h;
  if (config.coordinateSpace === "centered_pixels") {
    xmin = Math.round(xmin * width - width / 2);
    xmax = Math.round(xmax * width - width / 2);
    ymin = Math.round(ymin * height - height / 2);
    ymax = Math.round(ymax * height - height / 2);
  } else {
    xmin = Math.round(xmin * 1000);
    xmax = Math.round(xmax * 1000);
    ymin = Math.round(ymin * 1000);
    ymax = Math.round(ymax * 1000);
  }
  return config.order === "xy" ? [xmin, ymin, xmax, ymax] : [ymin, xmin, ymax, xmax];
}

export function parseBBoxDocument(mode, payload, width = 1024, height = 1024) {
  const source = unwrapBBoxPayload(payload);
  if (mode === "moss_image") {
    return {
      highLevelDescription: String(source?.summary?.caption || ""),
      backgroundDescription: "",
      summaryMeta: Array.isArray(source?.summary?.meta) ? source.summary.meta.map(String) : [],
      stylePalette: [],
      boxes: (Array.isArray(source?.items) ? source.items : []).map((item, index) => nativeBoxToNeutral(mode, item, index, width, height)),
    };
  }
  const decomp = source?.compositional_deconstruction || {};
  const elements = Array.isArray(decomp.elements) ? decomp.elements : Array.isArray(source?.elements) ? source.elements : [];
  return {
    highLevelDescription: String(source?.high_level_description || ""),
    backgroundDescription: String(decomp.background || ""),
    summaryMeta: [],
    stylePalette: Array.isArray(source?.style_description?.color_palette) ? source.style_description.color_palette.map(String) : [],
    boxes: elements.map((item, index) => nativeBoxToNeutral(mode, item, index, width, height)),
  };
}

export function serializeBBoxDocument(mode, document, width = 1024, height = 1024) {
  const boxes = Array.isArray(document?.boxes) ? document.boxes : [];
  if (mode === "moss_image") {
    return {
      summary: {
        meta: Array.isArray(document?.summaryMeta) && document.summaryMeta.length ? document.summaryMeta.map(String) : ["image"],
        canvas: "single",
        caption: String(document?.highLevelDescription || document?.backgroundDescription || ""),
      },
      items: boxes.map((box) => ({
        label: box.type === "text" ? "text" : "object",
        caption: String(box.desc || ""),
        ...(box.type === "text" && box.text ? { text: String(box.text) } : {}),
        bbox: neutralBoxToNativeBbox(mode, box, width, height),
      })),
      bbox_coord_space: "abs_centralized",
      bbox_format: "yxyx",
    };
  }
  const stylePalette = Array.isArray(document?.stylePalette) ? document.stylePalette.filter(Boolean) : [];
  return {
    high_level_description: String(document?.highLevelDescription || ""),
    style_description: stylePalette.length ? {
      aesthetics: "",
      lighting: "",
      medium: String(document?.detail || ""),
      color_palette: stylePalette.map((color) => String(color).toUpperCase()),
    } : undefined,
    compositional_deconstruction: {
      background: String(document?.backgroundDescription || ""),
      elements: boxes.map((box) => {
        const result = { type: box.type === "text" ? "text" : "obj", bbox: neutralBoxToNativeBbox(mode, box, width, height) };
        if (box.type === "text") result.text = String(box.text || "");
        result.desc = String(box.desc || "");
        const palette = (box.palette || []).filter(Boolean).slice(0, 5).map((color) => String(color).toUpperCase());
        if (palette.length) result.color_palette = palette;
        return result;
      }),
    },
  };
}
