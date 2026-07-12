from __future__ import annotations

import copy
import json
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Union


DEFAULT_PROFILES_DIR = Path(__file__).resolve().parents[1] / "profiles"
_PROFILE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


class OutputProfileError(ValueError):
    """Raised when an output profile cannot satisfy its semantic contract."""


def _fail(path: str, message: str) -> None:
    raise OutputProfileError(f"{path}: {message}")


def _field(value: Mapping[str, Any], name: str, path: str) -> Any:
    if name not in value:
        _fail(path, f"missing {name!r}")
    return value[name]


def _object(value: Any, path: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        _fail(path, "must be an object")
    return value


def _array(value: Any, path: str) -> list[Any]:
    if not isinstance(value, list) or not value:
        _fail(path, "must be a non-empty array")
    return value


def _string(value: Any, path: str) -> str:
    if not isinstance(value, str) or not value.strip():
        _fail(path, "must be a non-empty string")
    return value


def _integer(value: Any, path: str, *, positive: bool = False) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        _fail(path, "must be an integer")
    if positive and value < 1:
        _fail(path, "must be a positive integer")
    return value


def _number(value: Any, path: str, *, positive: bool = False) -> Union[int, float]:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        _fail(path, "must be a number")
    if positive and value <= 0:
        _fail(path, "must be positive")
    return value


def _boolean(value: Any, path: str) -> bool:
    if not isinstance(value, bool):
        _fail(path, "must be a boolean")
    return value


def validate_output_profile_semantics(profile: Any) -> dict[str, Any]:
    """Validate output-profile cross-field rules and return a detached copy."""

    root = _object(profile, "$")
    frame = _object(_field(root, "frame", "$"), "$.frame")
    frame_width = _integer(
        _field(frame, "width", "$.frame"), "$.frame.width", positive=True
    )
    frame_height = _integer(
        _field(frame, "height", "$.frame"), "$.frame.height", positive=True
    )

    directions = _array(_field(root, "directions", "$"), "$.directions")
    direction_ids: list[str] = []
    direction_codes: list[str] = []
    for index, raw_direction in enumerate(directions):
        path = f"$.directions[{index}]"
        direction = _object(raw_direction, path)
        direction_ids.append(_string(_field(direction, "id", path), f"{path}.id"))
        direction_codes.append(
            _string(_field(direction, "code", path), f"{path}.code")
        )
    if len(direction_ids) != len(set(direction_ids)):
        _fail("$.directions", "direction ids must be unique")
    if len(direction_codes) != len(set(direction_codes)):
        _fail("$.directions", "direction codes must be unique")

    actions = _array(_field(root, "actions", "$"), "$.actions")
    action_ids: set[str] = set()
    for index, raw_action in enumerate(actions):
        path = f"$.actions[{index}]"
        action = _object(raw_action, path)
        action_id = _string(_field(action, "id", path), f"{path}.id")
        if action_id in action_ids:
            _fail(f"{path}.id", "action ids must be unique")
        action_ids.add(action_id)

        frame_count = _integer(
            _field(action, "frame_count", path),
            f"{path}.frame_count",
            positive=True,
        )
        fps = _number(_field(action, "fps", path), f"{path}.fps", positive=True)
        if fps > 120:
            _fail(f"{path}.fps", "must be at most 120")
        loop = _boolean(_field(action, "loop", path), f"{path}.loop")
        terminal = _boolean(_field(action, "terminal", path), f"{path}.terminal")
        if loop and terminal:
            _fail(path, "terminal actions cannot loop")
        beats = _array(_field(action, "beats", path), f"{path}.beats")
        beats = [
            _string(beat, f"{path}.beats[{beat_index}]")
            for beat_index, beat in enumerate(beats)
        ]
        if len(beats) != frame_count:
            _fail(f"{path}.beats", "length must equal frame_count")
        _string(
            _field(action, "prompt_contract", path),
            f"{path}.prompt_contract",
        )
        _string(_field(action, "acceptance", path), f"{path}.acceptance")
        layout = _object(
            _field(action, "sheet_layout", path), f"{path}.sheet_layout"
        )
        layout_path = f"{path}.sheet_layout"

        direction_order = _array(
            _field(layout, "direction_order", layout_path),
            f"{layout_path}.direction_order",
        )
        direction_order = [
            _string(item, f"{layout_path}.direction_order[{item_index}]")
            for item_index, item in enumerate(direction_order)
        ]
        if direction_order != direction_ids:
            _fail(
                f"{layout_path}.direction_order",
                "must exactly match the profile direction ids",
            )

        frame_order = _array(
            _field(layout, "frame_order", layout_path),
            f"{layout_path}.frame_order",
        )
        frame_order = [
            _integer(item, f"{layout_path}.frame_order[{item_index}]")
            for item_index, item in enumerate(frame_order)
        ]
        if len(frame_order) != frame_count or any(
            frame_number != expected
            for expected, frame_number in enumerate(frame_order)
        ):
            _fail(
                f"{layout_path}.frame_order",
                "must equal 0 through frame_count - 1",
            )

        columns = _integer(
            _field(layout, "columns", layout_path), f"{layout_path}.columns"
        )
        if columns != frame_count:
            _fail(f"{layout_path}.columns", "must equal frame_count")
        rows = _integer(_field(layout, "rows", layout_path), f"{layout_path}.rows")
        if rows != len(direction_ids):
            _fail(f"{layout_path}.rows", "must equal the direction count")

        pivot = _object(_field(action, "pivot", path), f"{path}.pivot")
        pivot_x = _integer(_field(pivot, "x", f"{path}.pivot"), f"{path}.pivot.x")
        pivot_y = _integer(_field(pivot, "y", f"{path}.pivot"), f"{path}.pivot.y")
        if not 0 <= pivot_x < frame_width or not 0 <= pivot_y < frame_height:
            _fail(f"{path}.pivot", "must be inside the frame")

    try:
        return copy.deepcopy(dict(root))
    except Exception as exc:
        raise OutputProfileError(f"$: cannot detach output profile ({exc})") from exc


def load_output_profile(path: Union[str, Path]) -> dict[str, Any]:
    """Read and semantically validate an output profile from an injected path."""

    profile_path = Path(path)
    try:
        profile = json.loads(profile_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise OutputProfileError(
            f"{profile_path}: cannot load output profile ({exc})"
        ) from exc
    return validate_output_profile_semantics(profile)


def load_output_profile_by_id(
    profile_id: str,
    profiles_dir: Union[str, Path] = DEFAULT_PROFILES_DIR,
) -> dict[str, Any]:
    """Load one installed profile by portable id without accepting paths."""

    if not isinstance(profile_id, str) or _PROFILE_ID.fullmatch(profile_id) is None:
        raise OutputProfileError("profile id must be a portable identifier")
    profile = load_output_profile(Path(profiles_dir) / f"{profile_id}.json")
    if profile.get("id") != profile_id:
        raise OutputProfileError("$.id: must match the requested profile id")
    return profile


def action_recipe_for_profile(
    profile: Mapping[str, Any], action_id: str
) -> dict[str, Any]:
    """Return a detached action recipe from an already validated profile."""

    for action in profile.get("actions", []):
        if isinstance(action, Mapping) and action.get("id") == action_id:
            return copy.deepcopy(dict(action))
    raise OutputProfileError(f"unknown action {action_id!r} in output profile")
