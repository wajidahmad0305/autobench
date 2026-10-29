"""Small shared helpers used across the package."""

from __future__ import annotations

from typing import Any

import structlog

log = structlog.get_logger(__name__)


def normalize_arguments(arguments: dict[str, Any]) -> dict[str, Any]:
    """Unwrap any single-element list argument into its scalar.

    e.g. ``{"email": ["a@b.com"]}`` -> ``{"email": "a@b.com"}``. Some models
    (notably ``qwen/qwen3.8-27b``) wrap scalar tool arguments in a one-element
    list. Both :mod:`autobench.environment` (before dispatch) and
    :mod:`autobench.evaluator` (before ``args_contain`` matching) apply this.
    """
    normalized: dict[str, Any] = {}
    for key, value in arguments.items():
        if isinstance(value, list) and len(value) == 1:
            log.debug("unwrap_single_element_list", key=key, original=value, unwrapped=value[0])
            normalized[key] = value[0]
        else:
            normalized[key] = value
    return normalized

