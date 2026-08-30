from __future__ import annotations

from dataclasses import asdict, dataclass, field


FORMAT_NATURAL = "natural"
FORMAT_TAGS = "tags"
FORMAT_JSON = "json"
ALL_FORMATS = (FORMAT_NATURAL, FORMAT_TAGS, FORMAT_JSON)

GENERATION_TEXT_TO_IMAGE = "text_to_image"
GENERATION_IMAGE_TO_IMAGE = "image_to_image"
GENERATION_TEXT_TO_VIDEO = "text_to_video"
GENERATION_FIRST_FRAME_TO_VIDEO = "first_frame_to_video"
GENERATION_FIRST_LAST_FRAME_TO_VIDEO = "first_last_frame_to_video"
GENERATION_LAST_FRAME_TO_VIDEO = "last_frame_to_video"
GENERATION_REFERENCE_TO_VIDEO = "reference_to_video"
GENERATION_VIDEO_TO_VIDEO = "video_to_video"
ALL_GENERATION_TYPES = (
    GENERATION_TEXT_TO_IMAGE,
    GENERATION_IMAGE_TO_IMAGE,
    GENERATION_TEXT_TO_VIDEO,
    GENERATION_FIRST_FRAME_TO_VIDEO,
    GENERATION_FIRST_LAST_FRAME_TO_VIDEO,
    GENERATION_LAST_FRAME_TO_VIDEO,
    GENERATION_REFERENCE_TO_VIDEO,
    GENERATION_VIDEO_TO_VIDEO,
)
GENERATION_TYPE_LABELS = {
    GENERATION_TEXT_TO_IMAGE: "Text to Image",
    GENERATION_IMAGE_TO_IMAGE: "Image to Image",
    GENERATION_TEXT_TO_VIDEO: "Text to Video",
    GENERATION_FIRST_FRAME_TO_VIDEO: "First Frame to Video",
    GENERATION_FIRST_LAST_FRAME_TO_VIDEO: "First-Last Frame to Video",
    GENERATION_LAST_FRAME_TO_VIDEO: "Last Frame to Video",
    GENERATION_REFERENCE_TO_VIDEO: "Reference to Video",
    GENERATION_VIDEO_TO_VIDEO: "Video to Video",
}
GENERATION_IMAGE_COUNTS = {
    GENERATION_TEXT_TO_IMAGE: (0, 0),
    GENERATION_IMAGE_TO_IMAGE: (1, None),
    GENERATION_TEXT_TO_VIDEO: (0, 0),
    GENERATION_FIRST_FRAME_TO_VIDEO: (1, 1),
    GENERATION_FIRST_LAST_FRAME_TO_VIDEO: (2, 2),
    GENERATION_LAST_FRAME_TO_VIDEO: (1, 1),
    GENERATION_REFERENCE_TO_VIDEO: (1, None),
    GENERATION_VIDEO_TO_VIDEO: (1, None),
}
MAX_AUTHORING_IMAGES = 9

IMAGE_STATE_SUPPORTED_WITH_IMAGE = "supported_with_image"
IMAGE_STATE_SUPPORTED_WITHOUT_IMAGE = "supported_without_image"
IMAGE_STATE_UNSUPPORTED_WITH_IMAGE_GUIDANCE = "unsupported_with_image_guidance"
ALL_IMAGE_STATES = (
    IMAGE_STATE_SUPPORTED_WITH_IMAGE,
    IMAGE_STATE_SUPPORTED_WITHOUT_IMAGE,
    IMAGE_STATE_UNSUPPORTED_WITH_IMAGE_GUIDANCE,
)


@dataclass(frozen=True)
class InstructionBlock:
    """Editable model-facing text plus UI-only metadata."""

    title: str
    text: str
    source: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class PromptFormatRule:
    enabled: bool
    common_rules: InstructionBlock
    common_guide: InstructionBlock

    @property
    def common_instructions(self) -> str:
        """Compatibility view for code that only needs the selected text."""

        return "\n\n".join(
            block.text for block in (self.common_rules, self.common_guide) if block.text.strip()
        )

    def to_dict(self) -> dict:
        return {
            "enabled": self.enabled,
            "common_rules": self.common_rules.to_dict(),
            "common_guide": self.common_guide.to_dict(),
        }


@dataclass(frozen=True)
class OutputContractRule:
    negative_off: str
    negative_on: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class GenerationPathRule:
    label: str
    path_rules: InstructionBlock
    path_guide: InstructionBlock
    image_state_blocks: dict[str, InstructionBlock]
    output_contracts: dict[str, OutputContractRule]

    @property
    def instructions(self) -> str:
        """Compatibility view for selected generation-path text."""

        return "\n\n".join(
            block.text for block in (self.path_rules, self.path_guide) if block.text.strip()
        )

    def to_dict(self) -> dict:
        return {
            "label": self.label,
            "path_rules": self.path_rules.to_dict(),
            "path_guide": self.path_guide.to_dict(),
            "image_state_blocks": {
                key: block.to_dict() for key, block in self.image_state_blocks.items()
            },
            "output_contracts": {
                key: contract.to_dict() for key, contract in self.output_contracts.items()
            },
        }


@dataclass(frozen=True)
class PromptProfile:
    key: str
    label: str
    media_type: str
    default_format: str
    negative_supported: bool
    json_supported: bool
    notes: str
    formats: dict[str, PromptFormatRule]
    default_generation_type: str
    generation_paths: dict[str, GenerationPathRule]
    engine: str = "standard"
    jsonx_config: dict = field(default_factory=dict)

    def enabled_formats(self) -> tuple[str, ...]:
        return tuple(format_key for format_key in ALL_FORMATS if self.formats.get(format_key) and self.formats[format_key].enabled)

    def to_dict(self) -> dict:
        data = asdict(self)
        data["formats"] = {key: rule.to_dict() for key, rule in self.formats.items()}
        data["generation_paths"] = {
            key: rule.to_dict() for key, rule in self.generation_paths.items()
        }
        return data


def all_profiles() -> dict[str, PromptProfile]:
    profiles: dict[str, PromptProfile] = {}
    from .reference_store import standard_profiles

    for metadata in standard_profiles():
        profile = _standard_profile_from_metadata(metadata)
        profiles[profile.key] = profile
    from .jsonx_profile.reference_store import jsonx_profiles

    for metadata in jsonx_profiles():
        profile = _jsonx_profile_from_metadata(metadata)
        profiles[profile.key] = profile
    return profiles


def _standard_profile_from_metadata(metadata: dict) -> PromptProfile:
    enabled_format_keys = tuple(str(item) for item in metadata.get("enabled_formats", ()))
    formats = {
        key: PromptFormatRule(
            enabled=key in enabled_format_keys,
            common_rules=InstructionBlock("", "", ""),
            common_guide=InstructionBlock("", "", ""),
        )
        for key in ALL_FORMATS
    }
    generation_paths = {
        key: GenerationPathRule(
            label=GENERATION_TYPE_LABELS.get(key, key.replace("_", " ").title()),
            path_rules=InstructionBlock("", "", ""),
            path_guide=InstructionBlock("", "", ""),
            image_state_blocks={
                state: InstructionBlock("", "", "") for state in ALL_IMAGE_STATES
            },
            output_contracts={
                format_key: OutputContractRule("", "") for format_key in ALL_FORMATS
            },
        )
        for key in metadata.get("enabled_generation_types", ())
    }
    enabled_formats_value = tuple(key for key in ALL_FORMATS if formats[key].enabled)
    return PromptProfile(
        key=str(metadata.get("key") or ""),
        label=str(metadata.get("label") or metadata.get("key") or ""),
        media_type=str(metadata.get("media_type") or "image"),
        default_format=str(metadata.get("default_format") or (enabled_formats_value[0] if enabled_formats_value else FORMAT_NATURAL)),
        negative_supported=bool(metadata.get("negative_supported")),
        json_supported=FORMAT_JSON in enabled_formats_value,
        notes="",
        formats=formats,
        default_generation_type=str(metadata.get("default_generation_type") or next(iter(generation_paths), GENERATION_TEXT_TO_IMAGE)),
        generation_paths=generation_paths,
        engine="standard",
    )


def _jsonx_profile_from_metadata(metadata: dict) -> PromptProfile:
    profile = _standard_profile_from_metadata(metadata)
    return PromptProfile(
        key=profile.key,
        label=profile.label,
        media_type=profile.media_type,
        default_format=profile.default_format,
        negative_supported=profile.negative_supported,
        json_supported=profile.json_supported,
        notes="",
        formats=profile.formats,
        default_generation_type=profile.default_generation_type,
        generation_paths=profile.generation_paths,
        engine="jsonx",
        jsonx_config=dict(metadata.get("defaults") or {}),
    )


def profile_options() -> list[str]:
    return list(all_profiles())


def format_options() -> list[str]:
    return list(ALL_FORMATS)


def get_profile(key: str) -> PromptProfile:
    profiles = all_profiles()
    normalized = str(key or "").strip()
    if not normalized:
        return profiles["ideogram4"]
    if normalized not in profiles:
        raise ValueError(f"Unknown Unified PrompterX profile: {normalized}.")
    return profiles[normalized]


def enabled_formats(profile: PromptProfile) -> tuple[str, ...]:
    return tuple(format_key for format_key in ALL_FORMATS if profile.formats.get(format_key) and profile.formats[format_key].enabled)


def normalize_format(profile_key: str, prompt_format: str) -> str:
    profile = get_profile(profile_key)
    formats = enabled_formats(profile)
    if prompt_format in formats:
        return prompt_format
    if profile.default_format in formats:
        return profile.default_format
    return formats[0] if formats else FORMAT_NATURAL


def supports_negative(profile_key: str) -> bool:
    return get_profile(profile_key).negative_supported


def generation_types(profile_key: str) -> tuple[str, ...]:
    return tuple(get_profile(profile_key).generation_paths)


def normalize_generation_type(profile_key: str, generation_type: str) -> str:
    profile = get_profile(profile_key)
    if not str(generation_type or "").strip():
        if profile.default_generation_type in profile.generation_paths:
            return profile.default_generation_type
        return next(iter(profile.generation_paths), GENERATION_TEXT_TO_IMAGE)
    if generation_type in profile.generation_paths:
        return generation_type
    raise ValueError(
        f"Generation type '{generation_type}' is not supported by {profile.label}."
    )


def validate_generation_image_count(generation_type: str, image_count: int) -> None:
    """Validate the authoring node's media ceiling, not downstream path counts."""

    if generation_type not in GENERATION_IMAGE_COUNTS:
        raise ValueError(f"Unknown generation type: {generation_type}.")
    count = max(0, int(image_count or 0))
    if count > MAX_AUTHORING_IMAGES:
        raise ValueError(
            f"Unified PrompterX accepts at most {MAX_AUTHORING_IMAGES} authoring images; received {count}."
        )


def generation_path_supports_images(generation_type: str) -> bool:
    _minimum, maximum = GENERATION_IMAGE_COUNTS[generation_type]
    return maximum != 0


def resolve_image_state(generation_type: str, image_count: int) -> str | None:
    """Resolve which single image-state block is model-facing for this call."""

    has_images = max(0, int(image_count or 0)) > 0
    if generation_path_supports_images(generation_type):
        return (
            IMAGE_STATE_SUPPORTED_WITH_IMAGE
            if has_images
            else IMAGE_STATE_SUPPORTED_WITHOUT_IMAGE
        )
    if has_images:
        return IMAGE_STATE_UNSUPPORTED_WITH_IMAGE_GUIDANCE
    return None


def effective_generation_images(generation_type: str, images):
    """Return connected images as authoring evidence for every generation path."""

    normalized = list(images or [])
    validate_generation_image_count(generation_type, len(normalized))
    return normalized, 0


def effective_generation_image_count(generation_type: str, image_count: int) -> tuple[int, int]:
    """Return ``(submitted_count, ignored_count)`` for authoring evidence."""

    count = max(0, int(image_count or 0))
    validate_generation_image_count(generation_type, count)
    return count, 0


def profiles_payload() -> dict:
    from .reference_store import REFERENCE_SCHEMA_VERSION
    from .jsonx_profile.reference_store import JSONX_REFERENCE_SCHEMA_VERSION

    profiles = all_profiles()
    profile_items = []
    for profile in profiles.values():
        if profile.engine == "standard":
            profile_items.append({
                "key": profile.key,
                "label": profile.label,
                "media_type": profile.media_type,
                "default_format": profile.default_format,
                "negative_supported": profile.negative_supported,
                "json_supported": profile.json_supported,
                "notes": "",
                "engine": "standard",
                "formats": {
                    key: {"enabled": rule.enabled} for key, rule in profile.formats.items()
                },
                "default_generation_type": profile.default_generation_type,
                "generation_paths": {
                    key: {"label": rule.label} for key, rule in profile.generation_paths.items()
                },
                "jsonx_config": {},
            })
        else:
            profile_items.append({
                "key": profile.key,
                "label": profile.label,
                "media_type": profile.media_type,
                "default_format": profile.default_format,
                "negative_supported": profile.negative_supported,
                "json_supported": profile.json_supported,
                "notes": "",
                "engine": "jsonx",
                "formats": {
                    key: {"enabled": rule.enabled} for key, rule in profile.formats.items()
                },
                "default_generation_type": profile.default_generation_type,
                "generation_paths": {
                    key: {"label": rule.label} for key, rule in profile.generation_paths.items()
                },
                "jsonx_config": dict(profile.jsonx_config),
            })
    return {
        "schema_version": 7,
        "reference_schema_version": REFERENCE_SCHEMA_VERSION,
        "jsonx_reference_schema_version": JSONX_REFERENCE_SCHEMA_VERSION,
        "profiles": profile_items,
        "formats": format_options(),
        "generation_types": [
            {"key": key, "label": GENERATION_TYPE_LABELS[key]}
            for key in ALL_GENERATION_TYPES
        ],
    }
