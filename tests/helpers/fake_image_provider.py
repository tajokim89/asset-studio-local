from __future__ import annotations

import binascii
import hashlib
import struct
import zlib
from pathlib import Path

from asset_studio.provider import ProviderArtifact, ProviderError, ProviderRequest


def _png_chunk(kind: bytes, payload: bytes) -> bytes:
    checksum = binascii.crc32(kind + payload) & 0xFFFFFFFF
    return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", checksum)


def deterministic_png(prompt: str, aspect_ratio: str = "square") -> bytes:
    dimensions = {
        "landscape": (24, 16),
        "portrait": (16, 24),
        "square": (16, 16),
    }
    width, height = dimensions.get(aspect_ratio, dimensions["square"])
    digest = hashlib.sha256(prompt.encode("utf-8")).digest()
    rows = bytearray()
    for y in range(height):
        rows.append(0)
        for x in range(width):
            index = (x * 3 + y * 5) % len(digest)
            border = x < 2 or y < 2 or x >= width - 2 or y >= height - 2
            rows.extend((digest[index], digest[(index + 7) % 32], digest[(index + 13) % 32], 0 if border else 255))

    header = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + _png_chunk(b"IHDR", header)
        + _png_chunk(b"IDAT", zlib.compress(bytes(rows), level=9))
        + _png_chunk(b"IEND", b"")
    )


class FakeImageProvider:
    name = "fake-image-provider"
    display_name = "Fake Image Provider"

    def __init__(self, output_dir: Path, *, failure: dict | None = None):
        self.output_dir = Path(output_dir)
        self.failure = dict(failure) if failure else None
        self.calls: list[dict] = []

    def is_available(self) -> bool:
        return self.failure is None

    def health(self) -> dict:
        if self.failure is not None:
            return {
                "status": "unavailable",
                "available": False,
                "provider": self.name,
                "error_code": self.failure.get("error_type", "provider_error"),
            }
        return {"status": "ready", "available": True, "provider": self.name}

    def capabilities(self) -> dict:
        return {"modalities": ["text", "image"], "max_reference_images": 4}

    def default_model(self) -> str:
        return "fake-image-v1"

    def _raise_canonical_failure(self) -> None:
        if self.failure is None:
            return
        code = self.failure.get("error_type", "provider_error")
        if not isinstance(code, str) or not code.isidentifier() or not code.islower():
            code = "provider_error"
        message = self.failure.get("error", "provider failed")
        if not isinstance(message, str) or not message.strip():
            message = "provider failed"
        raise ProviderError(
            code,
            message,
            provider=self.name,
            retryable=code in {"rate_limited", "timeout", "unavailable"},
        )

    def _canonical_image(self, request: ProviderRequest, operation: str) -> ProviderArtifact:
        self._raise_canonical_failure()
        self.output_dir.mkdir(parents=True, exist_ok=True)
        seed = "\n".join(
            (
                operation,
                request.prompt,
                *request.input_artifacts,
                request.mask_artifact or "",
            )
        )
        digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:12]
        image_path = self.output_dir / f"fake_{operation}_{len(self.calls):03d}_{digest}.png"
        image_path.write_bytes(deterministic_png(seed, request.aspect_ratio))
        return ProviderArtifact(
            kind="image",
            provider=self.name,
            media_type="image/png",
            uri=str(image_path),
            model=request.model or self.default_model(),
            request_id=request.request_id,
            metadata={
                "operation": operation,
                "aspect_ratio": request.aspect_ratio,
                "input_artifact_count": len(request.input_artifacts),
            },
        )

    def generate(
        self,
        request=None,
        aspect_ratio: str = "square",
        *,
        image_url: str | None = None,
        reference_image_urls: list[str] | None = None,
        prompt: str | None = None,
        **_kwargs,
    ):
        if request is None:
            request = prompt
        elif prompt is not None:
            raise TypeError("provide request or prompt, not both")
        if isinstance(request, ProviderRequest):
            self.calls.append({"operation": "generate", "request": request})
            return self._canonical_image(request, "generate")
        if not isinstance(request, str):
            raise TypeError("legacy prompt must be a string")

        call = {"prompt": request, "aspect_ratio": aspect_ratio}
        if image_url is not None:
            call["image_url"] = image_url
        if reference_image_urls is not None:
            call["reference_image_urls"] = list(reference_image_urls)
        self.calls.append(call)

        if self.failure is not None:
            return {"success": False, **self.failure, "provider": self.name}

        self.output_dir.mkdir(parents=True, exist_ok=True)
        digest = hashlib.sha256(request.encode("utf-8")).hexdigest()[:12]
        image_path = self.output_dir / f"fake_{len(self.calls):03d}_{digest}.png"
        image_path.write_bytes(deterministic_png(request, aspect_ratio))
        return {
            "success": True,
            "image": str(image_path),
            "model": self.default_model(),
            "provider": self.name,
        }

    def edit(self, request: ProviderRequest) -> ProviderArtifact:
        if not isinstance(request, ProviderRequest):
            raise TypeError("edit requires ProviderRequest")
        self.calls.append({"operation": "edit", "request": request})
        if not request.input_artifacts:
            raise ProviderError(
                "invalid_request",
                "edit requires at least one input artifact",
                provider=self.name,
            )
        return self._canonical_image(request, "edit")

    def review(self, request: ProviderRequest) -> ProviderArtifact:
        if not isinstance(request, ProviderRequest):
            raise TypeError("review requires ProviderRequest")
        self.calls.append({"operation": "review", "request": request})
        if not request.input_artifacts:
            raise ProviderError(
                "invalid_request",
                "review requires at least one input artifact",
                provider=self.name,
            )
        self._raise_canonical_failure()
        digest = hashlib.sha256(
            "\n".join((request.prompt, *request.input_artifacts)).encode("utf-8")
        ).hexdigest()
        return ProviderArtifact(
            kind="review",
            provider=self.name,
            media_type="application/json",
            data={"verdict": "pass", "digest": digest},
            model=request.model or self.default_model(),
            request_id=request.request_id,
            metadata={"operation": "review"},
        )
