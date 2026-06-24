from __future__ import annotations

from dataclasses import asdict, dataclass


FORMAT_NATURAL = "natural"
FORMAT_TAGS = "tags"
FORMAT_JSON = "json"
ALL_FORMATS = (FORMAT_NATURAL, FORMAT_TAGS, FORMAT_JSON)


@dataclass(frozen=True)
class PromptFormatRule:
    enabled: bool
    common_instructions: str
    output_contract_negative_off: str
    output_contract_negative_on: str
    with_image_reference_instructions: str
    without_image_reference_instructions: str

    def to_dict(self) -> dict:
        return asdict(self)


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

    def enabled_formats(self) -> tuple[str, ...]:
        return tuple(format_key for format_key in ALL_FORMATS if self.formats.get(format_key) and self.formats[format_key].enabled)

    def to_dict(self) -> dict:
        data = asdict(self)
        data["formats"] = {key: rule.to_dict() for key, rule in self.formats.items()}
        return data


def all_profiles() -> dict[str, PromptProfile]:
    try:
        from .profile_config import merged_profiles

        return merged_profiles()
    except Exception:
        return {}


def profile_options() -> list[str]:
    return list(all_profiles())


def format_options() -> list[str]:
    return list(ALL_FORMATS)


def get_profile(key: str) -> PromptProfile:
    profiles = all_profiles()
    return profiles.get(key) or profiles["ideogram4"]


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


def profiles_payload() -> dict:
    profiles = all_profiles()
    return {
        "profiles": [profile.to_dict() for profile in profiles.values()],
        "formats": format_options(),
    }
