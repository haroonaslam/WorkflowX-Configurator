from __future__ import annotations

import hashlib
import json
import logging
import os
import random
import tempfile
from typing import Any, ClassVar, NamedTuple

logger = logging.getLogger(__name__)


CATEGORY = "WorkflowX_Configurator"
MODE_OPTIONS = ("Active", "Bypass", "Mute", "Ignore")
SCOPE_OPTIONS = ("Group Configurator", "Selector Mute", "Selector Bypass", "Ignore")
SELECTOR_TYPES = {"KVGC_ConfigSelector", "KVGC_ConfigSelectorAdvanced"}
INACTIVE_WORKFLOW_MODES = {2, 4}
UNLOAD_MODEL_OPTIONS = (
    "Text Encoder",
    "Diffusion Model / UNet",
    "VAE",
    "CLIP Vision",
    "Other Loaded Models",
    "All Loaded Models",
)
UNLOAD_DEVICE_OPTIONS = ("Current Device", "All Devices")

try:
    import comfy.samplers

    SAMPLER_OPTIONS = comfy.samplers.KSampler.SAMPLERS
    SCHEDULER_OPTIONS = comfy.samplers.KSampler.SCHEDULERS
except Exception:
    SAMPLER_OPTIONS = [
        "euler",
        "euler_ancestral",
        "heun",
        "dpm_2",
        "dpm_2_ancestral",
        "lms",
        "dpm_fast",
        "dpm_adaptive",
        "dpmpp_2s_ancestral",
        "dpmpp_sde",
        "dpmpp_2m",
        "dpmpp_2m_sde",
        "ddim",
    ]
    SCHEDULER_OPTIONS = [
        "normal",
        "karras",
        "exponential",
        "sgm_uniform",
        "simple",
        "ddim_uniform",
        "beta",
    ]

try:
    from comfy.comfy_types.node_typing import IO

    ANY_TYPE = IO.ANY
except Exception:
    ANY_TYPE = "*"


class _FlexibleOptionalInputType(dict):
    """Optional input map that accepts dynamic serialized widget values."""

    def __init__(self, input_type: Any, data: dict[str, Any] | None = None) -> None:
        super().__init__()
        self.input_type = input_type
        self.data = data or {}
        for key, value in self.data.items():
            self[key] = value

    def __getitem__(self, key: str) -> Any:
        if key in self.data:
            return self.data[key]
        return (self.input_type,)

    def __contains__(self, key: object) -> bool:
        return True


class _Rect(NamedTuple):
    x: float
    y: float
    width: float
    height: float


class _ConfigContext(NamedTuple):
    selected_config: str
    config_modes: dict[str, str]
    groups: list[dict[str, Any]]


class _TypedKeyValueBase:
    TYPE_NAME: ClassVar[str]
    SET_CLASS_TYPE: ClassVar[str]
    DEFAULT_VALUE: ClassVar[Any]
    VALUE_INPUT: ClassVar[tuple[str, dict[str, Any]]]
    RETURN_TYPE: ClassVar[str]
    RETURN_NAME: ClassVar[str]

    @staticmethod
    def _normalize_key(key: str) -> str:
        return str(key).strip()

    @classmethod
    def _coerce(cls, value: Any) -> Any:
        return value

    @classmethod
    def _workflow_nodes(cls, extra_pnginfo: dict[str, Any] | None) -> list[dict[str, Any]]:
        if not isinstance(extra_pnginfo, dict):
            return []

        workflow = extra_pnginfo.get("workflow")
        if not isinstance(workflow, dict):
            return []

        nodes = workflow.get("nodes")
        if not isinstance(nodes, list):
            return []

        return [node for node in nodes if isinstance(node, dict)]

    @classmethod
    def _workflow(cls, extra_pnginfo: dict[str, Any] | None) -> dict[str, Any]:
        if not isinstance(extra_pnginfo, dict):
            return {}

        workflow = extra_pnginfo.get("workflow")
        return workflow if isinstance(workflow, dict) else {}

    @classmethod
    def _workflow_groups(cls, extra_pnginfo: dict[str, Any] | None) -> list[dict[str, Any]]:
        groups = cls._workflow(extra_pnginfo).get("groups")
        if not isinstance(groups, list):
            return []
        return [group for group in groups if isinstance(group, dict)]

    @classmethod
    def _prompt_nodes(cls, prompt: dict[str, Any] | None) -> list[dict[str, Any]]:
        if not isinstance(prompt, dict):
            return []

        nodes: list[dict[str, Any]] = []
        for node_id, data in prompt.items():
            if not isinstance(data, dict):
                continue
            node = dict(data)
            node.setdefault("id", node_id)
            nodes.append(node)
        return nodes

    @classmethod
    def _sort_id(cls, node: dict[str, Any]) -> int:
        node_id = node.get("id", 0)
        try:
            return int(node_id)
        except (TypeError, ValueError):
            return 0

    @classmethod
    def _is_active_workflow_node(cls, node: dict[str, Any]) -> bool:
        mode = node.get("mode", 0)
        try:
            return int(mode) not in INACTIVE_WORKFLOW_MODES
        except (TypeError, ValueError):
            return True

    @staticmethod
    def _widget_values(node: dict[str, Any]) -> list[Any]:
        widgets_values = node.get("widgets_values")
        return widgets_values if isinstance(widgets_values, list) else []

    @classmethod
    def _group_title(cls, group: dict[str, Any]) -> str:
        return str(group.get("title", "")).strip()

    @staticmethod
    def _rect_from_pair(pos: Any, size: Any) -> _Rect | None:
        if not isinstance(pos, list | tuple) or not isinstance(size, list | tuple):
            return None
        if len(pos) < 2 or len(size) < 2:
            return None
        try:
            return _Rect(float(pos[0]), float(pos[1]), float(size[0]), float(size[1]))
        except (TypeError, ValueError):
            return None

    @classmethod
    def _node_rect(cls, node: dict[str, Any]) -> _Rect | None:
        return cls._rect_from_pair(node.get("pos"), node.get("size"))

    @classmethod
    def _group_rect(cls, group: dict[str, Any]) -> _Rect | None:
        bounding = group.get("bounding")
        if isinstance(bounding, list | tuple) and len(bounding) >= 4:
            try:
                return _Rect(
                    float(bounding[0]),
                    float(bounding[1]),
                    float(bounding[2]),
                    float(bounding[3]),
                )
            except (TypeError, ValueError):
                return None

        rect = cls._rect_from_pair(group.get("pos"), group.get("size"))
        if rect is not None:
            return rect

        try:
            return _Rect(
                float(group["x"]),
                float(group["y"]),
                float(group.get("width", group.get("w"))),
                float(group.get("height", group.get("h"))),
            )
        except (KeyError, TypeError, ValueError):
            return None

    @staticmethod
    def _rects_intersect(first: _Rect, second: _Rect) -> bool:
        return (
            first.x < second.x + second.width
            and first.x + first.width > second.x
            and first.y < second.y + second.height
            and first.y + first.height > second.y
        )

    @classmethod
    def _selected_config_name(cls, nodes: list[dict[str, Any]]) -> str:
        selectors: list[tuple[int, str]] = []
        for node in nodes:
            if node.get("type") not in SELECTOR_TYPES:
                continue

            widgets_values = cls._widget_values(node)
            if not widgets_values:
                continue

            selected_config = str(widgets_values[0]).strip()
            if selected_config:
                selectors.append((cls._sort_id(node), selected_config))

        if not selectors:
            return ""

        return sorted(selectors, key=lambda item: item[0])[-1][1]

    @classmethod
    def _configurator_modes(cls, nodes: list[dict[str, Any]], selected_config: str) -> dict[str, str]:
        configs: list[tuple[int, dict[str, str]]] = []
        for node in nodes:
            if node.get("type") != "KVGC_GroupConfigurator":
                continue

            widgets_values = cls._widget_values(node)
            if len(widgets_values) < 2:
                continue

            config_name = str(widgets_values[0]).strip()
            if config_name != selected_config:
                continue

            try:
                parsed = json.loads(str(widgets_values[1] or "{}"))
            except json.JSONDecodeError:
                continue

            if not isinstance(parsed, dict):
                continue

            modes = {
                str(group_name): str(mode)
                for group_name, mode in parsed.items()
                if str(mode) in MODE_OPTIONS
            }
            configs.append((cls._sort_id(node), modes))

        if not configs:
            return {}

        return sorted(configs, key=lambda item: item[0])[-1][1]

    @classmethod
    def _config_context(cls, extra_pnginfo: dict[str, Any] | None) -> _ConfigContext | None:
        nodes = cls._workflow_nodes(extra_pnginfo)
        selected_config = cls._selected_config_name(nodes)
        if not selected_config:
            return None

        config_modes = cls._configurator_modes(nodes, selected_config)
        if not config_modes:
            return None

        return _ConfigContext(
            selected_config=selected_config,
            config_modes=config_modes,
            groups=cls._workflow_groups(extra_pnginfo),
        )

    @classmethod
    def _configured_group_modes_for_node(
        cls,
        node: dict[str, Any],
        context: _ConfigContext,
    ) -> list[str]:
        node_rect = cls._node_rect(node)
        if node_rect is None:
            return []

        modes: list[str] = []
        for group in context.groups:
            title = cls._group_title(group)
            if title not in context.config_modes:
                continue

            group_rect = cls._group_rect(group)
            if group_rect is None:
                continue

            if cls._rects_intersect(node_rect, group_rect):
                mode = context.config_modes[title]
                if mode != "Ignore":
                    modes.append(mode)

        return modes

    @classmethod
    def _is_selected_config_candidate(
        cls,
        node: dict[str, Any],
        context: _ConfigContext,
    ) -> bool:
        modes = cls._configured_group_modes_for_node(node, context)
        if not modes:
            return True
        return "Active" in modes

    @classmethod
    def _selected_config_candidate_priority(
        cls,
        node: dict[str, Any],
        context: _ConfigContext,
    ) -> int | None:
        modes = cls._configured_group_modes_for_node(node, context)
        if not modes:
            return 0
        if "Active" in modes:
            return 1
        return None

    @classmethod
    def _read_from_workflow_node(cls, node: dict[str, Any]) -> tuple[str, Any] | None:
        widgets_values = node.get("widgets_values")
        if not isinstance(widgets_values, list) or len(widgets_values) < 2:
            return None

        key = cls._normalize_key(widgets_values[0])
        if not key:
            return None

        return key, widgets_values[1]

    @classmethod
    def _read_from_prompt_node(cls, node: dict[str, Any]) -> tuple[str, Any] | None:
        inputs = node.get("inputs")
        if not isinstance(inputs, dict):
            return None

        key = cls._normalize_key(inputs.get("key", ""))
        if not key:
            return None

        return key, inputs.get("value", cls.DEFAULT_VALUE)

    @classmethod
    def _matching_set_nodes(
        cls,
        key: str,
        prompt: dict[str, Any] | None,
        extra_pnginfo: dict[str, Any] | None,
    ) -> list[tuple[int, Any]]:
        matches: list[tuple[int, Any]] = []
        prioritized_matches: list[tuple[int, int, Any]] = []
        context = cls._config_context(extra_pnginfo)

        for node in cls._workflow_nodes(extra_pnginfo):
            if node.get("type") != cls.SET_CLASS_TYPE:
                continue

            if context is None and not cls._is_active_workflow_node(node):
                continue

            read = cls._read_from_workflow_node(node)
            if read is None:
                continue

            found_key, value = read
            if found_key == key:
                sort_id = cls._sort_id(node)
                if context is not None:
                    priority = cls._selected_config_candidate_priority(node, context)
                    if priority is None:
                        continue
                    prioritized_matches.append((priority, sort_id, value))
                else:
                    matches.append((sort_id, value))

        if prioritized_matches:
            best_priority = min(priority for priority, _, _ in prioritized_matches)
            return sorted(
                [
                    (sort_id, value)
                    for priority, sort_id, value in prioritized_matches
                    if priority == best_priority
                ],
                key=lambda item: item[0],
            )

        if matches:
            return sorted(matches, key=lambda item: item[0])

        for node in cls._prompt_nodes(prompt):
            if node.get("class_type") != cls.SET_CLASS_TYPE:
                continue

            read = cls._read_from_prompt_node(node)
            if read is None:
                continue

            found_key, value = read
            if found_key == key:
                matches.append((cls._sort_id(node), value))

        return sorted(matches, key=lambda item: item[0])

    @classmethod
    def _lookup(
        cls,
        key: str,
        prompt: dict[str, Any] | None,
        extra_pnginfo: dict[str, Any] | None,
    ) -> Any:
        clean_key = cls._normalize_key(key)
        if not clean_key:
            raise ValueError(f"{cls.TYPE_NAME} key cannot be empty.")

        matches = cls._matching_set_nodes(clean_key, prompt, extra_pnginfo)
        if not matches:
            raise KeyError(
                f"No {cls.TYPE_NAME} value found for key '{clean_key}'. "
                f"Add a Set {cls.TYPE_NAME} node with the same key to this workflow."
            )

        if len(matches) > 1:
            logger.warning(
                "Multiple Set %s nodes found for key '%s'; using node id %s.",
                cls.TYPE_NAME,
                clean_key,
                matches[-1][0],
            )

        return cls._coerce(matches[-1][1])

    @classmethod
    def _fingerprint(
        cls,
        key: str,
        prompt: dict[str, Any] | None,
        extra_pnginfo: dict[str, Any] | None,
        resolved_value: Any = None,
        resolved_config: str = "",
        resolved_digest: str = "",
    ) -> str:
        clean_key = cls._normalize_key(key)
        context = cls._config_context(extra_pnginfo)
        matches = cls._matching_set_nodes(clean_key, prompt, extra_pnginfo)
        payload = {
            "type": cls.TYPE_NAME,
            "key": clean_key,
            "matches": matches,
            "selected_config": context.selected_config if context else "",
            "config_modes": context.config_modes if context else {},
            "resolved_value": resolved_value,
            "resolved_config": resolved_config,
            "resolved_digest": resolved_digest,
        }
        encoded = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    @classmethod
    def _expected_resolved_digest(
        cls,
        key: str,
        resolved_config: str,
        resolved_value: Any,
    ) -> str:
        payload = {
            "config": str(resolved_config or ""),
            "key": cls._normalize_key(key),
            "type": cls.TYPE_NAME,
            "value": resolved_value,
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
        return f"workflowx:{encoded}"

    @classmethod
    def _has_valid_resolved_value(
        cls,
        key: str,
        resolved_value: Any,
        resolved_config: str,
        resolved_digest: str,
    ) -> bool:
        if not str(resolved_digest or ""):
            return False

        expected = cls._expected_resolved_digest(key, resolved_config, resolved_value)
        return str(resolved_digest) == expected


class _SetBase(_TypedKeyValueBase):
    CATEGORY = CATEGORY
    FUNCTION = "set_value"
    RETURN_TYPES = ()

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "key": ("STRING", {"default": "", "placeholder": "key"}),
                "value": cls.VALUE_INPUT,
            }
        }

    def set_value(self, key: str, value: Any) -> tuple[()]:
        if not self._normalize_key(key):
            raise ValueError(f"Set {self.TYPE_NAME} key cannot be empty.")
        return ()


class _GetBase(_TypedKeyValueBase):
    CATEGORY = CATEGORY
    FUNCTION = "get_value"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "key": ("STRING", {"default": "", "placeholder": "key"}),
                "resolved_value": ("STRING", {"default": "", "placeholder": "internal"}),
                "resolved_config": ("STRING", {"default": "", "placeholder": "internal"}),
                "resolved_digest": ("STRING", {"default": "", "placeholder": "internal"}),
            },
            "hidden": {
                "prompt": "PROMPT",
                "extra_pnginfo": "EXTRA_PNGINFO",
            },
        }

    def get_value(
        self,
        key: str,
        resolved_value: Any = "",
        resolved_config: str = "",
        resolved_digest: str = "",
        prompt: dict[str, Any] | None = None,
        extra_pnginfo: dict[str, Any] | None = None,
    ) -> tuple[Any]:
        if self._has_valid_resolved_value(key, resolved_value, resolved_config, resolved_digest):
            return (self._coerce(resolved_value),)
        return (self._lookup(key, prompt, extra_pnginfo),)

    @classmethod
    def IS_CHANGED(
        cls,
        key: str,
        resolved_value: Any = "",
        resolved_config: str = "",
        resolved_digest: str = "",
        prompt: dict[str, Any] | None = None,
        extra_pnginfo: dict[str, Any] | None = None,
    ) -> str:
        return cls._fingerprint(
            key,
            prompt,
            extra_pnginfo,
            resolved_value,
            resolved_config,
            resolved_digest,
        )


class _IntValueMixin(_TypedKeyValueBase):
    TYPE_NAME = "Int"
    DEFAULT_VALUE = 0
    VALUE_INPUT = ("INT", {"default": 0, "min": -2**31, "max": 2**31 - 1})
    RETURN_TYPE = "INT"
    RETURN_NAME = "int"

    @classmethod
    def _coerce(cls, value: Any) -> int:
        return int(value)


class _FloatValueMixin(_TypedKeyValueBase):
    TYPE_NAME = "Float"
    DEFAULT_VALUE = 0.0
    VALUE_INPUT = ("FLOAT", {"default": 0.0, "step": 0.01, "round": False})
    RETURN_TYPE = "FLOAT"
    RETURN_NAME = "float"

    @classmethod
    def _coerce(cls, value: Any) -> float:
        return float(value)


class _StringValueMixin(_TypedKeyValueBase):
    TYPE_NAME = "String"
    DEFAULT_VALUE = ""
    VALUE_INPUT = ("STRING", {"default": "", "placeholder": "value"})
    RETURN_TYPE = "STRING"
    RETURN_NAME = "string"

    @classmethod
    def _coerce(cls, value: Any) -> str:
        return str(value)


class _TextValueMixin(_TypedKeyValueBase):
    TYPE_NAME = "Text"
    DEFAULT_VALUE = ""
    VALUE_INPUT = ("STRING", {"default": "", "multiline": True})
    RETURN_TYPE = "STRING"
    RETURN_NAME = "text"

    @classmethod
    def _coerce(cls, value: Any) -> str:
        return str(value)


class _BooleanValueMixin(_TypedKeyValueBase):
    TYPE_NAME = "Boolean"
    DEFAULT_VALUE = False
    VALUE_INPUT = ("BOOLEAN", {"default": False})
    RETURN_TYPE = "BOOLEAN"
    RETURN_NAME = "boolean"

    @classmethod
    def _coerce(cls, value: Any) -> bool:
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "on"}
        return bool(value)


class _SamplerValueMixin(_TypedKeyValueBase):
    TYPE_NAME = "Sampler"
    DEFAULT_VALUE = SAMPLER_OPTIONS[0] if SAMPLER_OPTIONS else ""
    VALUE_INPUT = (SAMPLER_OPTIONS,)
    RETURN_TYPE = SAMPLER_OPTIONS
    RETURN_NAME = "sampler_name"

    @classmethod
    def _coerce(cls, value: Any) -> str:
        return str(value)


class _SchedulerValueMixin(_TypedKeyValueBase):
    TYPE_NAME = "Scheduler"
    DEFAULT_VALUE = SCHEDULER_OPTIONS[0] if SCHEDULER_OPTIONS else ""
    VALUE_INPUT = (SCHEDULER_OPTIONS,)
    RETURN_TYPE = SCHEDULER_OPTIONS
    RETURN_NAME = "scheduler"

    @classmethod
    def _coerce(cls, value: Any) -> str:
        return str(value)


class SetInt(_IntValueMixin, _SetBase):
    SET_CLASS_TYPE = "KVGC_SetInt"


class GetInt(_IntValueMixin, _GetBase):
    SET_CLASS_TYPE = "KVGC_SetInt"
    RETURN_TYPES = (_IntValueMixin.RETURN_TYPE,)
    RETURN_NAMES = (_IntValueMixin.RETURN_NAME,)


class SetFloat(_FloatValueMixin, _SetBase):
    SET_CLASS_TYPE = "KVGC_SetFloat"


class GetFloat(_FloatValueMixin, _GetBase):
    SET_CLASS_TYPE = "KVGC_SetFloat"
    RETURN_TYPES = (_FloatValueMixin.RETURN_TYPE,)
    RETURN_NAMES = (_FloatValueMixin.RETURN_NAME,)


class SetString(_StringValueMixin, _SetBase):
    SET_CLASS_TYPE = "KVGC_SetString"


class GetString(_StringValueMixin, _GetBase):
    SET_CLASS_TYPE = "KVGC_SetString"
    RETURN_TYPES = (_StringValueMixin.RETURN_TYPE,)
    RETURN_NAMES = (_StringValueMixin.RETURN_NAME,)


class SetText(_TextValueMixin, _SetBase):
    SET_CLASS_TYPE = "KVGC_SetText"


class GetText(_TextValueMixin, _GetBase):
    SET_CLASS_TYPE = "KVGC_SetText"
    RETURN_TYPES = (_TextValueMixin.RETURN_TYPE,)
    RETURN_NAMES = (_TextValueMixin.RETURN_NAME,)


class SetBoolean(_BooleanValueMixin, _SetBase):
    SET_CLASS_TYPE = "KVGC_SetBoolean"


class GetBoolean(_BooleanValueMixin, _GetBase):
    SET_CLASS_TYPE = "KVGC_SetBoolean"
    RETURN_TYPES = (_BooleanValueMixin.RETURN_TYPE,)
    RETURN_NAMES = (_BooleanValueMixin.RETURN_NAME,)


class SetSampler(_SamplerValueMixin, _SetBase):
    SET_CLASS_TYPE = "KVGC_SetSampler"


class GetSampler(_SamplerValueMixin, _GetBase):
    SET_CLASS_TYPE = "KVGC_SetSampler"
    RETURN_TYPES = (_SamplerValueMixin.RETURN_TYPE,)
    RETURN_NAMES = (_SamplerValueMixin.RETURN_NAME,)


class SetScheduler(_SchedulerValueMixin, _SetBase):
    SET_CLASS_TYPE = "KVGC_SetScheduler"


class GetScheduler(_SchedulerValueMixin, _GetBase):
    SET_CLASS_TYPE = "KVGC_SetScheduler"
    RETURN_TYPES = (_SchedulerValueMixin.RETURN_TYPE,)
    RETURN_NAMES = (_SchedulerValueMixin.RETURN_NAME,)


class SetRelay:
    CATEGORY = CATEGORY
    FUNCTION = "set_value"
    RETURN_TYPES = (ANY_TYPE,)
    RETURN_NAMES = ("value",)

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "key": ("STRING", {"default": "", "placeholder": "key"}),
                "value": (ANY_TYPE,),
            }
        }

    def set_value(self, key: str, value: Any) -> tuple[Any]:
        if not _TypedKeyValueBase._normalize_key(key):
            raise ValueError("Set Relay key cannot be empty.")
        return (value,)


class GetRelay:
    CATEGORY = CATEGORY
    FUNCTION = "get_value"
    RETURN_TYPES = (ANY_TYPE,)
    RETURN_NAMES = ("value",)

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "key": ("STRING", {"default": "", "placeholder": "key"}),
            },
            "optional": {
                "value": (ANY_TYPE,),
            },
        }

    def get_value(self, key: str, value: Any = None) -> tuple[Any]:
        clean_key = _TypedKeyValueBase._normalize_key(key)
        if not clean_key:
            raise ValueError("Get Relay key cannot be empty.")
        if value is None:
            raise ValueError(
                f"No Relay value found for key '{clean_key}'. "
                "Add a Set Relay with the same key in an active config group, "
                "or connect the Get Relay value input directly."
            )
        return (value,)


class UnloadModelsByType:
    DESCRIPTION = (
        "Unload currently resident ComfyUI models by type. Use it inline as a "
        "passthrough before CLIP Text Encode to unload the diffusion model, or "
        "after CLIP Text Encode to unload the text encoder before sampling."
    )

    CATEGORY = f"{CATEGORY}/VRAM"
    FUNCTION = "unload"
    RETURN_TYPES = (ANY_TYPE, "MODEL", "CLIP", "VAE", "CONDITIONING", "STRING")
    RETURN_NAMES = ("trigger", "model", "clip", "vae", "conditioning", "status")

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "model_type": (
                    UNLOAD_MODEL_OPTIONS,
                    {"default": "Text Encoder"},
                ),
                "device_scope": (
                    UNLOAD_DEVICE_OPTIONS,
                    {"default": "Current Device"},
                ),
                "empty_cache": ("BOOLEAN", {"default": True}),
            },
            "optional": {
                "trigger": (ANY_TYPE,),
                "model": ("MODEL",),
                "clip": ("CLIP",),
                "vae": ("VAE",),
                "conditioning": ("CONDITIONING",),
            },
        }

    @classmethod
    def IS_CHANGED(cls, *args: Any, **kwargs: Any) -> float:
        return float("NaN")

    @staticmethod
    def _patcher_from_loaded_model(loaded_model: Any) -> Any | None:
        try:
            return loaded_model.model
        except Exception:
            return None

    @staticmethod
    def _real_model(patcher: Any) -> Any | None:
        return getattr(patcher, "model", None)

    @classmethod
    def _is_text_encoder(cls, patcher: Any) -> bool:
        return bool(getattr(patcher, "is_clip", False))

    @classmethod
    def _is_clip_vision(cls, patcher: Any) -> bool:
        model = cls._real_model(patcher)
        class_name = model.__class__.__name__.lower() if model is not None else ""
        module_name = model.__class__.__module__.lower() if model is not None else ""
        return "clipvision" in class_name or "clip_vision" in module_name

    @classmethod
    def _is_vae(cls, patcher: Any) -> bool:
        model = cls._real_model(patcher)
        class_name = model.__class__.__name__.lower() if model is not None else ""
        module_name = model.__class__.__module__.lower() if model is not None else ""
        return (
            "vae" in class_name
            or "autoencoder" in class_name
            or ".vae" in module_name
            or "autoencoder" in module_name
        )

    @classmethod
    def _is_diffusion_model(cls, patcher: Any) -> bool:
        if cls._is_text_encoder(patcher) or cls._is_vae(patcher) or cls._is_clip_vision(patcher):
            return False

        model = cls._real_model(patcher)
        if model is None:
            return False

        return (
            hasattr(model, "diffusion_model")
            or hasattr(model, "model_sampling")
            or hasattr(model, "model_type")
        )

    @classmethod
    def _matches_target(cls, loaded_model: Any, model_type: str) -> bool:
        patcher = cls._patcher_from_loaded_model(loaded_model)
        if patcher is None:
            return False

        if model_type == "All Loaded Models":
            return True
        if model_type == "Text Encoder":
            return cls._is_text_encoder(patcher)
        if model_type == "Diffusion Model / UNet":
            return cls._is_diffusion_model(patcher)
        if model_type == "VAE":
            return cls._is_vae(patcher)
        if model_type == "CLIP Vision":
            return cls._is_clip_vision(patcher)
        if model_type == "Other Loaded Models":
            return not (
                cls._is_text_encoder(patcher)
                or cls._is_diffusion_model(patcher)
                or cls._is_vae(patcher)
                or cls._is_clip_vision(patcher)
            )
        return False

    @classmethod
    def _describe_loaded_model(cls, loaded_model: Any) -> str:
        patcher = cls._patcher_from_loaded_model(loaded_model)
        model = cls._real_model(patcher) if patcher is not None else None
        if model is not None:
            return model.__class__.__name__
        if patcher is not None:
            return patcher.__class__.__name__
        return "unknown"

    @staticmethod
    def _passthrough_value(
        trigger: Any = None,
        model: Any = None,
        clip: Any = None,
        vae: Any = None,
        conditioning: Any = None,
    ) -> Any:
        if trigger is not None:
            return trigger
        for value in (conditioning, model, clip, vae):
            if value is not None:
                return value
        return None

    def unload(
        self,
        model_type: str,
        device_scope: str,
        empty_cache: bool,
        trigger: Any = None,
        model: Any = None,
        clip: Any = None,
        vae: Any = None,
        conditioning: Any = None,
    ) -> tuple[Any, Any, Any, Any, Any, str]:
        try:
            import comfy.model_management as model_management
        except Exception as exc:
            status = f"WorkflowX unload skipped: could not import ComfyUI model management ({exc})."
            logger.warning(status)
            return (
                self._passthrough_value(trigger, model, clip, vae, conditioning),
                model,
                clip,
                vae,
                conditioning,
                status,
            )

        loaded_models = list(getattr(model_management, "current_loaded_models", []))
        keep_loaded = [
            loaded_model
            for loaded_model in loaded_models
            if not self._matches_target(loaded_model, model_type)
        ]

        devices = []
        if device_scope == "All Devices":
            try:
                devices = list(model_management.get_all_torch_devices())
            except Exception:
                devices = []
        if not devices:
            try:
                devices = [model_management.get_torch_device()]
            except Exception:
                devices = [None]

        unloaded = []
        for device in devices:
            try:
                unloaded.extend(model_management.free_memory(1e30, device, keep_loaded=keep_loaded))
            except Exception as exc:
                logger.warning("WorkflowX unload failed for %s on %s: %s", model_type, device, exc)

        if empty_cache:
            try:
                model_management.soft_empty_cache(force=True)
            except TypeError:
                model_management.soft_empty_cache()
            except Exception as exc:
                logger.warning("WorkflowX unload could not empty cache: %s", exc)

        names = [self._describe_loaded_model(loaded_model) for loaded_model in unloaded]
        if names:
            preview = ", ".join(names[:8])
            if len(names) > 8:
                preview += f", +{len(names) - 8} more"
            status = f"WorkflowX unloaded {len(names)} {model_type}: {preview}"
        else:
            status = f"WorkflowX unloaded 0 {model_type}."
        logger.info(status)

        return (
            self._passthrough_value(trigger, model, clip, vae, conditioning),
            model,
            clip,
            vae,
            conditioning,
            status,
        )


class LoraX:
    DESCRIPTION = (
        "Load multiple LoRAs in order with one editable strength per row. The browser "
        "extension provides the rich picker and serializes dynamic lora_* rows."
    )

    CATEGORY = f"{CATEGORY}/Loaders"
    FUNCTION = "load_loras"
    RETURN_TYPES = ("MODEL", "CLIP", "STRING", "STRING")
    RETURN_NAMES = ("MODEL", "CLIP", "trigger_words", "loaded_loras")
    LORA_EXTENSIONS = (".safetensors", ".ckpt", ".pt", ".bin")

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "model": ("MODEL",),
            },
            "optional": _FlexibleOptionalInputType(
                ANY_TYPE,
                {
                    "clip": ("CLIP",),
                },
            ),
        }

    @staticmethod
    def _row_index(key: str) -> int:
        suffix = key.rsplit("_", 1)[-1]
        try:
            return int(suffix)
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def _as_float(value: Any, default: float = 0.0) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _as_bool(value: Any, default: bool = True) -> bool:
        if value is None:
            return default
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return bool(value)
        if isinstance(value, str):
            return value.strip().lower() not in {"0", "false", "no", "off", ""}
        return bool(value)

    @classmethod
    def _strip_lora_extension(cls, name: str) -> str:
        normalized = str(name or "").replace("\\", "/").strip()
        lower = normalized.lower()
        for ext in cls.LORA_EXTENSIONS:
            if lower.endswith(ext):
                return normalized[: -len(ext)]
        return normalized

    @classmethod
    def _lora_syntax_name(cls, load_name: str) -> str:
        return cls._strip_lora_extension(load_name)

    @staticmethod
    def _first_present(data: dict[str, Any], *keys: str) -> Any:
        for key in keys:
            value = data.get(key)
            if value not in (None, ""):
                return value
        return None

    @classmethod
    def _trigger_words_from_value(cls, value: dict[str, Any]) -> list[str]:
        raw = cls._first_present(value, "trigger_words", "trained_words", "trainedWords")
        if raw is None:
            metadata = value.get("metadata")
            if isinstance(metadata, dict):
                raw = cls._first_present(metadata, "trigger_words", "trained_words", "trainedWords")
                civitai = metadata.get("civitai")
                if raw is None and isinstance(civitai, dict):
                    raw = civitai.get("trainedWords")

        if isinstance(raw, str):
            parts = [part.strip() for part in raw.replace(",,", ",").split(",")]
            return [part for part in parts if part]
        if isinstance(raw, list | tuple):
            return [str(part).strip() for part in raw if str(part).strip()]
        return []

    @classmethod
    def _entry_from_value(cls, value: Any) -> dict[str, Any] | None:
        if not isinstance(value, dict):
            return None

        enabled = cls._as_bool(
            cls._first_present(value, "on", "enabled", "active"),
            default=True,
        )
        if not enabled:
            return None

        load_name = cls._first_present(value, "load_name", "loadName", "lora", "name")
        if load_name is None:
            return None

        load_name = str(load_name).replace("\\", "/").strip()
        if not load_name or load_name.lower() == "none":
            return None

        model_strength = cls._as_float(
            cls._first_present(value, "strength_model", "model_strength", "modelStrength", "strength"),
            default=1.0,
        )

        return {
            "load_name": load_name,
            "display_name": str(cls._first_present(value, "display_name", "displayName", "model_name") or load_name),
            "model_strength": model_strength,
            "trigger_words": cls._trigger_words_from_value(value),
        }

    @classmethod
    def _collect_entries(cls, kwargs: dict[str, Any]) -> list[dict[str, Any]]:
        entries: list[dict[str, Any]] = []
        for key, value in sorted(kwargs.items(), key=lambda item: cls._row_index(str(item[0]))):
            if not str(key).lower().startswith("lora_"):
                continue
            entry = cls._entry_from_value(value)
            if entry is not None:
                entries.append(entry)
        return entries

    @classmethod
    def _resolve_lora_path(cls, load_name: str) -> str:
        if os.path.isfile(load_name):
            return load_name

        try:
            import folder_paths
        except Exception as exc:
            raise ValueError(f"LoraX could not import folder_paths to resolve '{load_name}'.") from exc

        candidates = [load_name]
        if not load_name.lower().endswith(cls.LORA_EXTENSIONS):
            candidates.extend(f"{load_name}{ext}" for ext in cls.LORA_EXTENSIONS)

        for candidate in candidates:
            try:
                resolved = folder_paths.get_full_path("loras", candidate)
            except Exception:
                resolved = None
            if resolved and os.path.isfile(resolved):
                return resolved

        raise ValueError(f"LoraX could not find LoRA '{load_name}'.")

    @classmethod
    def _load_lora_for_models(
        cls,
        model: Any,
        clip: Any,
        load_name: str,
        model_strength: float,
        applied_clip_weight: float,
    ) -> tuple[Any, Any]:
        try:
            import comfy.sd
            import comfy.utils
        except Exception as exc:
            raise RuntimeError(f"LoraX could not import ComfyUI LoRA loaders: {exc}") from exc

        lora_path = cls._resolve_lora_path(load_name)
        try:
            lora, lora_metadata = comfy.utils.load_torch_file(
                lora_path,
                safe_load=True,
                return_metadata=True,
            )
        except TypeError:
            lora = comfy.utils.load_torch_file(lora_path, safe_load=True)
            lora_metadata = None
        return comfy.sd.load_lora_for_models(
            model,
            clip,
            lora,
            model_strength,
            applied_clip_weight,
            lora_metadata=lora_metadata,
        )

    @classmethod
    def _format_loaded_lora(cls, entry: dict[str, Any]) -> str:
        name = cls._lora_syntax_name(entry["load_name"])
        model_strength = entry["model_strength"]
        return f"<lora:{name}:{model_strength:g}>"

    def load_loras(self, model: Any, clip: Any = None, **kwargs: Any) -> tuple[Any, Any, str, str]:
        loaded_loras: list[str] = []
        trigger_words: list[str] = []

        for entry in self._collect_entries(kwargs):
            model_strength = entry["model_strength"]
            if model_strength == 0:
                continue
            applied_clip_weight = 1.0 if clip is not None else 0.0

            model, clip = self._load_lora_for_models(
                model,
                clip,
                entry["load_name"],
                model_strength,
                applied_clip_weight,
            )
            loaded_loras.append(self._format_loaded_lora(entry))
            trigger_words.extend(entry["trigger_words"])

        return (
            model,
            clip,
            ",, ".join(trigger_words) if trigger_words else "",
            " ".join(loaded_loras),
        )


class GroupConfigurator:
    CATEGORY = CATEGORY
    FUNCTION = "configure"
    RETURN_TYPES = ()

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "config_name": ("STRING", {"default": "config1", "placeholder": "config name"}),
            },
            "optional": {
                "config_json": (
                    "STRING",
                    {
                        "default": "{}",
                        "tooltip": "Managed by the frontend extension. Maps group names to Active, Bypass, or Mute.",
                    },
                )
            },
        }

    def configure(self, config_name: str, config_json: str = "{}") -> tuple[()]:
        if not str(config_name).strip():
            raise ValueError("Group Configurator config_name cannot be empty.")

        try:
            parsed = json.loads(config_json or "{}")
        except json.JSONDecodeError as exc:
            raise ValueError(f"Group Configurator config_json is invalid JSON: {exc}") from exc

        if not isinstance(parsed, dict):
            raise ValueError("Group Configurator config_json must be a JSON object.")

        invalid_modes = {
            mode for mode in parsed.values() if mode not in MODE_OPTIONS
        }
        if invalid_modes:
            raise ValueError(
                "Group Configurator config_json contains invalid mode(s): "
                + ", ".join(sorted(map(str, invalid_modes)))
            )

        return ()


class ConfigSelector:
    CATEGORY = CATEGORY
    FUNCTION = "select"
    RETURN_TYPES = ()

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "selected_config": ("STRING", {"default": "", "placeholder": "config name"}),
                "console_output": (["no", "yes"], {"default": "no"}),
            }
        }

    def select(self, selected_config: str, console_output: str = "no") -> tuple[()]:
        if str(console_output) not in {"no", "yes"}:
            raise ValueError("Config Selector console_output must be 'no' or 'yes'.")
        return ()


class ConfigSelectorAdvanced:
    CATEGORY = CATEGORY
    FUNCTION = "select"
    RETURN_TYPES = ()

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "selected_config": ("STRING", {"default": "", "placeholder": "config name"}),
                "console_output": (["no", "yes"], {"default": "no"}),
            },
            "optional": {
                "advanced_state": (
                    "STRING",
                    {
                        "default": "{}",
                        "tooltip": "Managed by the frontend extension. Stores advanced selector mute and bypass switch states.",
                    },
                )
            },
        }

    def select(
        self,
        selected_config: str,
        console_output: str = "no",
        advanced_state: str = "{}",
    ) -> tuple[()]:
        if str(console_output) not in {"no", "yes"}:
            raise ValueError("Config Selector Advanced console_output must be 'no' or 'yes'.")

        try:
            parsed = json.loads(advanced_state or "{}")
        except json.JSONDecodeError as exc:
            raise ValueError(f"Config Selector Advanced advanced_state is invalid JSON: {exc}") from exc

        if not isinstance(parsed, dict):
            raise ValueError("Config Selector Advanced advanced_state must be a JSON object.")

        for section_name, section in parsed.items():
            if section_name not in {"mute", "bypass"}:
                raise ValueError(
                    "Config Selector Advanced advanced_state contains invalid section: "
                    + str(section_name)
                )
            if not isinstance(section, dict):
                raise ValueError(
                    "Config Selector Advanced advanced_state sections must be JSON objects."
                )
            invalid_values = {
                group_name: value
                for group_name, value in section.items()
                if not isinstance(group_name, str) or not isinstance(value, bool)
            }
            if invalid_values:
                raise ValueError(
                    "Config Selector Advanced advanced_state values must be booleans keyed by group name."
                )

        return ()


class GroupScopes:
    CATEGORY = CATEGORY
    FUNCTION = "configure"
    RETURN_TYPES = ()

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "optional": {
                "scopes_json": (
                    "STRING",
                    {
                        "default": "{}",
                        "tooltip": "Managed by the frontend extension. Maps group names to selector/configurator scope.",
                    },
                )
            },
        }

    def configure(self, scopes_json: str = "{}") -> tuple[()]:
        try:
            parsed = json.loads(scopes_json or "{}")
        except json.JSONDecodeError as exc:
            raise ValueError(f"Group Scopes scopes_json is invalid JSON: {exc}") from exc

        if not isinstance(parsed, dict):
            raise ValueError("Group Scopes scopes_json must be a JSON object.")

        invalid_scopes = {
            scope for scope in parsed.values() if scope not in SCOPE_OPTIONS
        }
        if invalid_scopes:
            raise ValueError(
                "Group Scopes scopes_json contains invalid scope(s): "
                + ", ".join(sorted(map(str, invalid_scopes)))
            )

        return ()


class ImageCompareEditX:
    DESCRIPTION = (
        "Compare two IMAGE inputs and edit a browser-side blend as image3. "
        "The node stores image1/image2 previews for a professional in-node "
        "compare and mask editor; image3 can be compared, copied, or saved "
        "from the editor without adding downstream graph outputs."
    )

    CATEGORY = f"{CATEGORY}/Image"
    FUNCTION = "compare_images"
    RETURN_TYPES = ()
    OUTPUT_NODE = True

    def __init__(self) -> None:
        self.output_dir = self._default_temp_directory()
        self.type = "temp"
        self.prefix_append = "_wfxcmpx_" + "".join(
            random.choice("abcdefghijklmnopqrstuvwxyz") for _ in range(5)
        )
        self.compress_level = 4

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "image1": (
                    "IMAGE",
                    {
                        "tooltip": "First source image. It becomes image1 in the compare/editor UI.",
                    },
                ),
                "image2": (
                    "IMAGE",
                    {
                        "tooltip": "Second source image. It becomes image2 in the compare/editor UI.",
                    },
                ),
            }
        }

    @staticmethod
    def _folder_paths_module() -> Any | None:
        try:
            import folder_paths
        except Exception:
            return None
        return folder_paths

    @classmethod
    def _default_temp_directory(cls) -> str:
        folder_paths = cls._folder_paths_module()
        if folder_paths is not None:
            try:
                return str(folder_paths.get_temp_directory())
            except Exception:
                pass
        return tempfile.gettempdir()

    @staticmethod
    def _first_frame(tensor: Any) -> Any:
        try:
            return tensor[0]
        except Exception:
            return tensor

    @classmethod
    def _tensor_to_pil(cls, tensor: Any) -> Any:
        import numpy as np
        from PIL import Image

        frame = cls._first_frame(tensor)
        if hasattr(frame, "detach"):
            frame = frame.detach()
        if hasattr(frame, "cpu"):
            frame = frame.cpu()
        if hasattr(frame, "numpy"):
            array = frame.numpy()
        else:
            array = np.asarray(frame)

        if array.ndim == 4:
            array = array[0]

        array = np.asarray(array)
        if array.dtype.kind == "f":
            array = array * 255.0
        array = np.clip(array, 0, 255).astype(np.uint8)

        if array.ndim == 2:
            return Image.fromarray(array)
        if array.ndim == 3 and array.shape[2] == 4:
            return Image.fromarray(array)
        if array.ndim == 3 and array.shape[2] >= 3:
            return Image.fromarray(array[:, :, :3])
        raise ValueError("Image Compare Edit X expected IMAGE tensors with HxWxC data.")

    def _save_image_refs(self, images: list[Any]) -> list[dict[str, str]]:
        prefix = "workflowx_image_compare_edit_x" + self.prefix_append
        folder_paths = self._folder_paths_module()

        if folder_paths is not None:
            full_output_folder, filename, counter, subfolder, _ = (
                folder_paths.get_save_image_path(
                    prefix,
                    self.output_dir,
                    images[0].width,
                    images[0].height,
                )
            )
        else:
            full_output_folder = self.output_dir
            filename = prefix
            counter = 1
            subfolder = ""

        os.makedirs(full_output_folder, exist_ok=True)

        results: list[dict[str, str]] = []
        for img in images:
            file = f"{filename}_{counter:05}_.png"
            img.save(
                os.path.join(full_output_folder, file),
                "PNG",
                compress_level=self.compress_level,
            )
            results.append(
                {
                    "filename": file,
                    "subfolder": subfolder,
                    "type": self.type,
                }
            )
            counter += 1
        return results

    def compare_images(self, image1: Any, image2: Any) -> dict[str, Any]:
        images = [self._tensor_to_pil(image1), self._tensor_to_pil(image2)]
        return {"ui": {"images": self._save_image_refs(images)}}


NODE_CLASS_MAPPINGS = {
    "KVGC_SetInt": SetInt,
    "KVGC_GetInt": GetInt,
    "KVGC_SetFloat": SetFloat,
    "KVGC_GetFloat": GetFloat,
    "KVGC_SetString": SetString,
    "KVGC_GetString": GetString,
    "KVGC_SetText": SetText,
    "KVGC_GetText": GetText,
    "KVGC_SetBoolean": SetBoolean,
    "KVGC_GetBoolean": GetBoolean,
    "KVGC_SetSampler": SetSampler,
    "KVGC_GetSampler": GetSampler,
    "KVGC_SetScheduler": SetScheduler,
    "KVGC_GetScheduler": GetScheduler,
    "KVGC_SetRelay": SetRelay,
    "KVGC_GetRelay": GetRelay,
    "KVGC_GroupConfigurator": GroupConfigurator,
    "KVGC_ConfigSelector": ConfigSelector,
    "KVGC_ConfigSelectorAdvanced": ConfigSelectorAdvanced,
    "KVGC_GroupScopes": GroupScopes,
    "KVGC_UnloadModelsByType": UnloadModelsByType,
    "KVGC_LoraX": LoraX,
    "KVGC_ImageCompareEditX": ImageCompareEditX,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "KVGC_SetInt": "Set Int",
    "KVGC_GetInt": "Get Int",
    "KVGC_SetFloat": "Set Float",
    "KVGC_GetFloat": "Get Float",
    "KVGC_SetString": "Set String",
    "KVGC_GetString": "Get String",
    "KVGC_SetText": "Set Text",
    "KVGC_GetText": "Get Text",
    "KVGC_SetBoolean": "Set Boolean",
    "KVGC_GetBoolean": "Get Boolean",
    "KVGC_SetSampler": "Set Sampler",
    "KVGC_GetSampler": "Get Sampler",
    "KVGC_SetScheduler": "Set Scheduler",
    "KVGC_GetScheduler": "Get Scheduler",
    "KVGC_SetRelay": "Set Relay",
    "KVGC_GetRelay": "Get Relay",
    "KVGC_GroupConfigurator": "Group Configurator",
    "KVGC_ConfigSelector": "Config Selector",
    "KVGC_ConfigSelectorAdvanced": "Config Selector Advanced",
    "KVGC_GroupScopes": "Group Scopes",
    "KVGC_UnloadModelsByType": "Unload Models By Type",
    "KVGC_LoraX": "LoraX",
    "KVGC_ImageCompareEditX": "Image Compare Edit X",
}
