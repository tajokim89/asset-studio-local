"""Provider-neutral adapter for Hermes image generation backends."""

from __future__ import annotations

import re
from collections.abc import Mapping as MappingABC
from pathlib import PurePosixPath
from typing import Mapping, Optional, Tuple
from urllib.parse import urlparse

from .provider import ProviderArtifact, ProviderError, ProviderRequest


_ROLE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
_UPSTREAM_ERROR = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
_MODEL = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$")
_RETRYABLE_ERRORS = frozenset({"rate_limited", "timeout", "unavailable"})
_SAFE_UPSTREAM_ERRORS = frozenset(
    {
        "auth_required",
        "empty_response",
        "invalid_argument",
        "invalid_image_input",
        "io_error",
        "missing_dependency",
        "rate_limited",
        "timeout",
        "unavailable",
    }
)
_SAFE_ERROR_MESSAGES = {
    "auth_required": "Hermes authentication is required",
    "empty_response": "Hermes returned no image",
    "invalid_argument": "Hermes rejected the image request",
    "invalid_image_input": "Hermes rejected an image input",
    "io_error": "Hermes could not store the generated image",
    "missing_dependency": "Hermes image generation is unavailable",
    "rate_limited": "Hermes image generation is rate limited",
    "timeout": "Hermes image generation timed out",
    "unavailable": "Hermes image generation is unavailable",
}


def _provider_error(
    code: str,
    message: str,
    *,
    retryable: bool = False,
    details: Optional[Mapping[str, object]] = None,
) -> ProviderError:
    return ProviderError(
        code,
        message,
        provider="hermes",
        retryable=retryable,
        details=details,
    )


def _default_roles(count: int) -> Tuple[str, ...]:
    if count < 1:
        return ()
    return ("primary",) + tuple(
        f"reference_{index}" for index in range(1, count)
    )


def _reference_roles(request: ProviderRequest) -> Tuple[str, ...]:
    value = request.options.get("reference_roles")
    if value is None:
        return _default_roles(len(request.input_artifacts))
    if isinstance(value, (str, bytes)) or not isinstance(value, (list, tuple)):
        raise _provider_error(
            "invalid_request",
            "reference_roles must be an ordered list",
        )
    if len(value) != len(request.input_artifacts):
        raise _provider_error(
            "invalid_request",
            "reference_roles must align with input_artifacts",
        )
    roles = tuple(value)
    if any(not isinstance(role, str) or _ROLE.fullmatch(role) is None for role in roles):
        raise _provider_error(
            "invalid_request",
            "reference_roles contains an invalid role",
        )
    return roles


def _media_type(image_uri: str) -> str:
    suffix = PurePosixPath(urlparse(image_uri).path).suffix.lower()
    return {
        ".gif": "image/gif",
        ".jpeg": "image/jpeg",
        ".jpg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
    }.get(suffix, "image/png")


class HermesProviderAdapter:
    """Translate canonical requests to Hermes' unified image provider surface."""

    name = "hermes"
    display_name = "Hermes Image Provider"

    def __init__(self, backend: object):
        if backend is None:
            raise TypeError("backend is required")
        self._backend = backend

    def _capability_snapshot(self) -> dict:
        method = getattr(self._backend, "capabilities", None)
        if not callable(method):
            raise _provider_error(
                "unsupported",
                "Hermes backend does not declare image capabilities",
            )
        try:
            raw = method()
        except Exception:
            raise _provider_error(
                "unavailable",
                "Hermes capabilities are unavailable",
                retryable=True,
            ) from None
        if not isinstance(raw, MappingABC):
            raise _provider_error(
                "unsupported",
                "Hermes backend returned invalid image capabilities",
            )

        raw_modalities = raw.get("modalities", ())
        if isinstance(raw_modalities, (str, bytes)):
            modalities = ()
        elif isinstance(raw_modalities, (list, tuple, set, frozenset)):
            modalities = tuple(
                value for value in raw_modalities if isinstance(value, str)
            )
        else:
            modalities = ()

        raw_maximum = raw.get("max_reference_images", 0)
        maximum = (
            raw_maximum
            if isinstance(raw_maximum, int)
            and not isinstance(raw_maximum, bool)
            and raw_maximum >= 0
            else 0
        )
        return {
            "modalities": modalities,
            "max_reference_images": maximum,
            "supports_edit_mask": raw.get("supports_edit_mask") is True,
        }

    def capabilities(self) -> dict:
        snapshot = self._capability_snapshot()
        return {
            "modalities": list(snapshot["modalities"]),
            "max_reference_images": snapshot["max_reference_images"],
            "supports_edit_mask": snapshot["supports_edit_mask"],
        }

    def health(self) -> dict:
        try:
            available_method = getattr(self._backend, "is_available", None)
            available = bool(available_method()) if callable(available_method) else False
            if not available:
                return {
                    "status": "unavailable",
                    "available": False,
                    "provider": self.name,
                    "reason": "auth_or_dependency_missing",
                }
            return {
                "status": "ready",
                "available": True,
                "provider": self.name,
                "capabilities": self.capabilities(),
            }
        except Exception:
            return {
                "status": "unavailable",
                "available": False,
                "provider": self.name,
                "reason": "provider_health_failed",
            }

    def _validate_request(self, request: ProviderRequest) -> Tuple[str, ...]:
        if not isinstance(request, ProviderRequest):
            raise TypeError("request must be a ProviderRequest")
        roles = _reference_roles(request)
        capabilities = self._capability_snapshot()
        reference_count = len(request.input_artifacts)

        if not reference_count and "text" not in capabilities["modalities"]:
            raise _provider_error(
                "unsupported",
                "Hermes backend does not support text generation",
            )
        if reference_count and "image" not in capabilities["modalities"]:
            raise _provider_error(
                "unsupported",
                "Hermes backend does not support image inputs",
            )
        maximum = capabilities["max_reference_images"]
        if reference_count > maximum:
            raise _provider_error(
                "unsupported",
                "Hermes backend reference limit exceeded",
                details={
                    "requested_reference_images": reference_count,
                    "max_reference_images": maximum,
                },
            )
        if request.mask_artifact is not None:
            if not request.input_artifacts:
                raise _provider_error(
                    "invalid_request",
                    "A mask requires an input image",
                )
            if not capabilities["supports_edit_mask"]:
                raise _provider_error(
                    "unsupported",
                    "Hermes backend does not support edit masks",
                )
        return roles

    def _safe_model(self, result: Mapping[str, object], request: ProviderRequest) -> Optional[str]:
        candidates = (result.get("model"), request.model)
        for candidate in candidates:
            if isinstance(candidate, str) and _MODEL.fullmatch(candidate):
                return candidate
        method = getattr(self._backend, "default_model", None)
        if callable(method):
            try:
                candidate = method()
            except Exception:
                return None
            if isinstance(candidate, str) and _MODEL.fullmatch(candidate):
                return candidate
        return None

    def _call(self, request: ProviderRequest, operation: str) -> ProviderArtifact:
        roles = self._validate_request(request)
        kwargs = {}
        if request.input_artifacts:
            kwargs["image_url"] = request.input_artifacts[0]
            if len(request.input_artifacts) > 1:
                kwargs["reference_image_urls"] = list(request.input_artifacts[1:])
            kwargs["reference_roles"] = list(roles)
        if request.mask_artifact is not None:
            kwargs["mask_image_url"] = request.mask_artifact

        generate = getattr(self._backend, "generate", None)
        if not callable(generate):
            raise _provider_error(
                "unsupported",
                "Hermes backend has no image generation surface",
            )
        try:
            result = generate(request.prompt, request.aspect_ratio, **kwargs)
        except Exception:
            raise _provider_error(
                "provider_error",
                "Hermes image provider failed",
            ) from None
        if not isinstance(result, MappingABC):
            raise _provider_error(
                "provider_error",
                "Hermes returned an invalid image response",
            )
        if result.get("success") is not True:
            upstream = result.get("error_type")
            code = (
                upstream
                if isinstance(upstream, str)
                and _UPSTREAM_ERROR.fullmatch(upstream)
                and upstream in _SAFE_UPSTREAM_ERRORS
                else "provider_error"
            )
            raise _provider_error(
                code,
                _SAFE_ERROR_MESSAGES.get(code, "Hermes image provider failed"),
                retryable=code in _RETRYABLE_ERRORS,
            )

        image_uri = result.get("image")
        if not isinstance(image_uri, str) or not image_uri.strip():
            raise _provider_error(
                "provider_error",
                "Hermes returned an invalid image response",
            )
        image_uri = image_uri.strip()
        return ProviderArtifact(
            kind="image",
            provider=self.name,
            media_type=_media_type(image_uri),
            uri=image_uri,
            model=self._safe_model(result, request),
            request_id=request.request_id,
            metadata={
                "operation": operation,
                "aspect_ratio": request.aspect_ratio,
                "input_artifact_count": len(request.input_artifacts),
                "reference_roles": roles,
                "mask_applied": request.mask_artifact is not None,
            },
        )

    def generate(self, request: ProviderRequest) -> ProviderArtifact:
        return self._call(request, "generate")

    def edit(self, request: ProviderRequest) -> ProviderArtifact:
        if not isinstance(request, ProviderRequest):
            raise TypeError("request must be a ProviderRequest")
        if not request.input_artifacts:
            raise _provider_error(
                "invalid_request",
                "Edit requires at least one input image",
            )
        return self._call(request, "edit")

    def review(self, request: ProviderRequest) -> ProviderArtifact:
        if not isinstance(request, ProviderRequest):
            raise TypeError("request must be a ProviderRequest")
        raise _provider_error(
            "unsupported",
            "Hermes image backend does not provide visual review",
        )


__all__ = ["HermesProviderAdapter"]
