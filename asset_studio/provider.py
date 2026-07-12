"""Provider-neutral image generation, editing, and review contracts."""

from __future__ import annotations

import math
import re
from collections.abc import Mapping as MappingABC
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Mapping, Optional, Protocol, Tuple, runtime_checkable


_ERROR_CODE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")


def _required_text(value: object, field_name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string")
    if not value.strip():
        raise ValueError(f"{field_name} must not be empty")
    return value


def _optional_text(value: object, field_name: str) -> Optional[str]:
    if value is None:
        return None
    return _required_text(value, field_name)


def _freeze_json(value: object, field_name: str, depth: int = 0) -> object:
    if depth > 32:
        raise ValueError(f"{field_name} exceeds the nesting limit")
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"{field_name} must contain finite numbers")
        return value
    if isinstance(value, (list, tuple)):
        return tuple(
            _freeze_json(item, f"{field_name}[{index}]", depth + 1)
            for index, item in enumerate(value)
        )
    if isinstance(value, MappingABC):
        frozen = {}
        for key, item in value.items():
            key = _required_text(key, f"{field_name} key")
            frozen[key] = _freeze_json(item, f"{field_name}.{key}", depth + 1)
        return MappingProxyType(frozen)
    raise TypeError(f"{field_name} must contain only JSON-compatible values")


def _freeze_mapping(value: object, field_name: str) -> Mapping[str, object]:
    if not isinstance(value, MappingABC):
        raise TypeError(f"{field_name} must be a mapping")
    frozen = _freeze_json(value, field_name)
    if not isinstance(frozen, MappingABC):
        raise TypeError(f"{field_name} must be a mapping")
    return frozen


def _thaw_json(value: object) -> object:
    if isinstance(value, MappingABC):
        return {key: _thaw_json(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw_json(item) for item in value]
    return value


@dataclass(frozen=True)
class ProviderRequest:
    """Canonical request accepted by every provider operation."""

    prompt: str
    aspect_ratio: str = "square"
    model: Optional[str] = None
    input_artifacts: Tuple[str, ...] = ()
    mask_artifact: Optional[str] = None
    options: Mapping[str, object] = field(default_factory=dict)
    request_id: Optional[str] = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "prompt", _required_text(self.prompt, "prompt"))
        object.__setattr__(
            self,
            "aspect_ratio",
            _required_text(self.aspect_ratio, "aspect_ratio"),
        )
        object.__setattr__(self, "model", _optional_text(self.model, "model"))
        if isinstance(self.input_artifacts, (str, bytes)):
            raise TypeError("input_artifacts must be a sequence of strings")
        try:
            input_artifacts = tuple(
                _required_text(value, "input_artifacts item")
                for value in self.input_artifacts
            )
        except TypeError as error:
            if "must be a string" in str(error):
                raise
            raise TypeError("input_artifacts must be a sequence of strings") from error
        object.__setattr__(self, "input_artifacts", input_artifacts)
        object.__setattr__(
            self,
            "mask_artifact",
            _optional_text(self.mask_artifact, "mask_artifact"),
        )
        object.__setattr__(self, "options", _freeze_mapping(self.options, "options"))
        object.__setattr__(
            self,
            "request_id",
            _optional_text(self.request_id, "request_id"),
        )


@dataclass(frozen=True)
class ProviderArtifact:
    """Canonical provider result with either a URI or structured data payload."""

    kind: str
    provider: str
    media_type: str
    uri: Optional[str] = None
    data: Optional[Mapping[str, object]] = None
    model: Optional[str] = None
    request_id: Optional[str] = None
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "kind", _required_text(self.kind, "kind"))
        object.__setattr__(self, "provider", _required_text(self.provider, "provider"))
        object.__setattr__(
            self,
            "media_type",
            _required_text(self.media_type, "media_type"),
        )
        if (self.uri is None) == (self.data is None):
            raise ValueError("artifact requires exactly one of uri or data")
        object.__setattr__(self, "uri", _optional_text(self.uri, "uri"))
        if self.data is not None:
            object.__setattr__(self, "data", _freeze_mapping(self.data, "data"))
        object.__setattr__(self, "model", _optional_text(self.model, "model"))
        object.__setattr__(
            self,
            "request_id",
            _optional_text(self.request_id, "request_id"),
        )
        object.__setattr__(self, "metadata", _freeze_mapping(self.metadata, "metadata"))


class ProviderError(RuntimeError):
    """Stable provider failure with a machine-readable code and retry policy."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        provider: Optional[str] = None,
        retryable: bool = False,
        details: Optional[Mapping[str, object]] = None,
    ) -> None:
        code = _required_text(code, "code")
        if _ERROR_CODE.fullmatch(code) is None:
            raise ValueError("code must be a lowercase machine-readable identifier")
        message = _required_text(message, "message")
        if not isinstance(retryable, bool):
            raise TypeError("retryable must be a boolean")
        self.code = code
        self.message = message
        self.provider = _optional_text(provider, "provider")
        self.retryable = retryable
        self.details = (
            _freeze_mapping(details, "details") if details is not None else MappingProxyType({})
        )
        super().__init__(message)

    def as_dict(self) -> dict:
        result = {
            "code": self.code,
            "message": self.message,
            "retryable": self.retryable,
        }
        if self.provider is not None:
            result["provider"] = self.provider
        if self.details:
            result["details"] = _thaw_json(self.details)
        return result


@runtime_checkable
class ImageProvider(Protocol):
    """Provider boundary used by generation, edit, and visual review routes."""

    name: str
    display_name: str

    def health(self) -> Mapping[str, object]:
        ...

    def capabilities(self) -> Mapping[str, object]:
        ...

    def generate(self, request: ProviderRequest) -> ProviderArtifact:
        ...

    def edit(self, request: ProviderRequest) -> ProviderArtifact:
        ...

    def review(self, request: ProviderRequest) -> ProviderArtifact:
        ...


__all__ = [
    "ImageProvider",
    "ProviderArtifact",
    "ProviderError",
    "ProviderRequest",
]
