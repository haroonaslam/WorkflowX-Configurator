"""Prompt token substitution.

Deliberately NOT ``str.format``. People write JSON-structured prompts, and a
literal ``{`` in the template would raise KeyError or IndexError. We substitute
an explicit whitelist by regex and leave every other brace untouched.
"""

from __future__ import annotations

import re
from typing import Dict

DEFAULT_PROMPT = (
    "Replace the {target} with the reference. Match the original lighting "
    "direction, colour temperature, and perspective. Preserve everything outside "
    "the mask exactly. Blend the edges seamlessly with no visible seam or colour "
    "shift."
)

TOKENS = ("width", "height", "caption", "target")
_PATTERN = re.compile(r"\{(" + "|".join(TOKENS) + r")\}")


def render(template: str, context: Dict[str, object]) -> str:
    """Substitute the whitelist. Everything else passes through verbatim."""

    def _sub(m: "re.Match") -> str:
        return str(context.get(m.group(1), ""))

    return _PATTERN.sub(_sub, template)
