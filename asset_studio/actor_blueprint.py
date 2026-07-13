"""Strict pose blueprints for deterministic humanoid sprite generation guides."""

from __future__ import annotations

import copy
import io
import re
from collections.abc import Mapping, Sequence
from typing import Any

from PIL import Image, ImageDraw, ImageFont


SCHEMA_VERSION = "asset-studio.pose-blueprint/v1"
HUMANOID_BIPED_TOPOLOGY = "humanoid-biped-v1"

JOINT_NAMES = (
    "head",
    "neck",
    "shoulder_l",
    "shoulder_r",
    "elbow_l",
    "elbow_r",
    "wrist_l",
    "wrist_r",
    "hand_l",
    "hand_r",
    "pelvis",
    "hip_l",
    "hip_r",
    "knee_l",
    "knee_r",
    "ankle_l",
    "ankle_r",
    "toe_l",
    "toe_r",
)

HAND_STATES = frozenset({"open", "fist", "grip", "hidden"})
FOOT_STATES = frozenset({"planted", "passing", "flight", "landing"})
FOOT_SIDES = frozenset({"left", "right", "both", "none"})
DIRECTIONS = frozenset({"N", "NE", "E", "SE", "S", "SW", "W", "NW"})

_IDENTIFIER = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
_TOP_LEVEL_KEYS = {
    "schema_version",
    "topology",
    "direction",
    "action",
    "beat_id",
    "frame_index",
    "canvas",
    "joints",
    "root",
    "baseline",
    "support_foot",
    "contact_foot",
    "hand_state_l",
    "hand_state_r",
    "foot_state_l",
    "foot_state_r",
    "weapon_contact",
    "equipment_anchors",
}


class PoseBlueprintError(ValueError):
    """Raised when a pose blueprint violates the humanoid-biped contract."""


def _fail(path: str, message: str) -> None:
    raise PoseBlueprintError(f"{path}: {message}")


def _strict_object(value: Any, path: str, keys: set[str]) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        _fail(path, "must be an object")
    actual = set(value)
    if actual != keys:
        missing = sorted(keys - actual)
        unknown = sorted(actual - keys)
        details = []
        if missing:
            details.append(f"missing {missing}")
        if unknown:
            details.append(f"unknown {unknown}")
        _fail(path, "; ".join(details))
    return value


def _integer(value: Any, path: str, *, minimum: int, maximum: int) -> int:
    if type(value) is not int or not minimum <= value <= maximum:
        _fail(path, f"must be an integer in {minimum}..{maximum}")
    return value


def _normalized(value: Any, path: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        _fail(path, "must be a normalized number")
    normalized = float(value)
    if not 0.0 <= normalized <= 1.0:
        _fail(path, "must be in 0..1")
    return normalized


def _enum(value: Any, path: str, choices: frozenset[str]) -> str:
    if value not in choices:
        _fail(path, f"must be one of {sorted(choices)}")
    return value


def _identifier(value: Any, path: str) -> str:
    if not isinstance(value, str) or _IDENTIFIER.fullmatch(value) is None:
        _fail(path, "must be a lowercase portable identifier")
    return value


def _validate_point(value: Any, path: str, *, visible: bool) -> dict[str, Any]:
    keys = {"x", "y", "visible"} if visible else {"x", "y"}
    point = _strict_object(value, path, keys)
    result = {
        "x": _normalized(point["x"], f"{path}.x"),
        "y": _normalized(point["y"], f"{path}.y"),
    }
    if visible:
        if type(point["visible"]) is not bool:
            _fail(f"{path}.visible", "must be a boolean")
        result["visible"] = point["visible"]
    return result


def validate_pose_blueprint(value: Any) -> dict[str, Any]:
    """Validate one strict ``humanoid-biped-v1`` blueprint and detach it."""

    blueprint = _strict_object(value, "$", _TOP_LEVEL_KEYS)
    if blueprint["schema_version"] != SCHEMA_VERSION:
        _fail("$.schema_version", f"must equal {SCHEMA_VERSION!r}")
    if blueprint["topology"] != HUMANOID_BIPED_TOPOLOGY:
        _fail("$.topology", f"must equal {HUMANOID_BIPED_TOPOLOGY!r}")
    _enum(blueprint["direction"], "$.direction", DIRECTIONS)
    action = _identifier(blueprint["action"], "$.action")
    if blueprint["beat_id"] in {"N", "L", "R"}:
        beat_id = blueprint["beat_id"]
    else:
        beat_id = _identifier(blueprint["beat_id"], "$.beat_id")
    _integer(blueprint["frame_index"], "$.frame_index", minimum=0, maximum=255)

    canvas = _strict_object(blueprint["canvas"], "$.canvas", {"width", "height"})
    width = _integer(canvas["width"], "$.canvas.width", minimum=8, maximum=1024)
    height = _integer(canvas["height"], "$.canvas.height", minimum=8, maximum=1024)

    raw_joints = blueprint["joints"]
    if not isinstance(raw_joints, list):
        _fail("$.joints", "must be an array")
    joints: dict[str, dict[str, Any]] = {}
    for index, raw_joint in enumerate(raw_joints):
        path = f"$.joints[{index}]"
        joint = _strict_object(raw_joint, path, {"name", "x", "y", "visible"})
        name = joint["name"]
        if name not in JOINT_NAMES:
            _fail(f"{path}.name", "is not a humanoid-biped-v1 joint")
        if name in joints:
            _fail(f"{path}.name", f"duplicate joint {name!r}")
        joints[name] = _validate_point(
            {key: joint[key] for key in ("x", "y", "visible")}, path, visible=True
        )
    missing_joints = sorted(set(JOINT_NAMES) - set(joints))
    if missing_joints:
        _fail("$.joints", f"missing {missing_joints}")

    root = _validate_point(blueprint["root"], "$.root", visible=False)
    baseline = _normalized(blueprint["baseline"], "$.baseline")
    if abs(root["y"] - baseline) > 1e-9:
        _fail("$.root.y", "must equal baseline")

    support = _enum(blueprint["support_foot"], "$.support_foot", FOOT_SIDES)
    contact = _enum(blueprint["contact_foot"], "$.contact_foot", FOOT_SIDES)
    hand_states = {
        "left": _enum(blueprint["hand_state_l"], "$.hand_state_l", HAND_STATES),
        "right": _enum(blueprint["hand_state_r"], "$.hand_state_r", HAND_STATES),
    }
    foot_states = {
        "left": _enum(blueprint["foot_state_l"], "$.foot_state_l", FOOT_STATES),
        "right": _enum(blueprint["foot_state_r"], "$.foot_state_r", FOOT_STATES),
    }

    for side, state in hand_states.items():
        visible = joints[f"hand_{side[0]}"]["visible"]
        if (state == "hidden") == visible:
            _fail(f"$.hand_state_{side[0]}", "must match hand visibility")

    if support == "none" and contact != "none":
        _fail("$.contact_foot", "must be none when support_foot is none")
    if support == "both" and contact != "both":
        _fail("$.contact_foot", "must match support_foot")
    if support in {"left", "right"} and contact not in {support, "both"}:
        _fail("$.contact_foot", "must match support_foot or include it as both")
    if support in {"left", "right"}:
        opposite = "right" if support == "left" else "left"
        if foot_states[support] not in {"planted", "landing"}:
            _fail(f"$.foot_state_{support[0]}", "support foot must be planted or landing")
        if contact == support and foot_states[opposite] in {"planted", "landing"}:
            _fail(f"$.foot_state_{opposite[0]}", "opposite foot cannot also carry support")
        if contact == "both" and foot_states[opposite] not in {"planted", "landing"}:
            _fail(f"$.foot_state_{opposite[0]}", "auxiliary contact foot must be planted or landing")
        toe = joints[f"toe_{support[0]}"]
        ankle = joints[f"ankle_{support[0]}"]
        if not toe["visible"] or not ankle["visible"]:
            _fail("$.joints", "support ankle and toe must be visible")
        if abs(toe["y"] - baseline) > 1.0 / max(1, height - 1):
            _fail(f"$.joints.toe_{support[0]}.y", "support toe must touch baseline")
        if contact == "both":
            opposite_toe = joints[f"toe_{opposite[0]}"]
            opposite_ankle = joints[f"ankle_{opposite[0]}"]
            if not opposite_toe["visible"] or not opposite_ankle["visible"]:
                _fail("$.joints", "auxiliary contact ankle and toe must be visible")
            if abs(opposite_toe["y"] - baseline) > 1.0 / max(1, height - 1):
                _fail(
                    f"$.joints.toe_{opposite[0]}.y",
                    "auxiliary contact toe must touch baseline",
                )
    elif support == "both":
        if set(foot_states.values()) != {"planted"}:
            _fail("$.foot_state_l", "both support feet must be planted")
        for side in ("l", "r"):
            if abs(joints[f"toe_{side}"]["y"] - baseline) > 1.0 / max(1, height - 1):
                _fail(f"$.joints.toe_{side}.y", "supported toe must touch baseline")
    elif any(state in {"planted", "landing"} for state in foot_states.values()):
        _fail("$.support_foot", "none cannot include a planted or landing foot")

    if action == "walk":
        expected_side = {"L": "left", "R": "right"}.get(beat_id, beat_id.split("-", 1)[0])
        if expected_side not in {"left", "right"}:
            _fail("$.beat_id", "walk beat must identify left or right support")
        if support != expected_side:
            _fail("$.support_foot", f"must be {expected_side!r} for beat {beat_id!r}")
        if contact != support:
            _fail("$.contact_foot", "walk contact must match support_foot")
    elif action == "idle" and support != "both":
        _fail("$.support_foot", "idle requires both feet planted")

    weapon_contact = _strict_object(
        blueprint["weapon_contact"], "$.weapon_contact", {"left", "right"}
    )
    for side in ("left", "right"):
        if type(weapon_contact[side]) is not bool:
            _fail(f"$.weapon_contact.{side}", "must be a boolean")
        if weapon_contact[side] and hand_states[side] != "grip":
            _fail(f"$.hand_state_{side[0]}", "weapon contact requires grip")

    anchors = blueprint["equipment_anchors"]
    if not isinstance(anchors, list):
        _fail("$.equipment_anchors", "must be an array")
    anchor_ids: set[str] = set()
    for index, raw_anchor in enumerate(anchors):
        path = f"$.equipment_anchors[{index}]"
        anchor = _strict_object(raw_anchor, path, {"id", "joint"})
        anchor_id = _identifier(anchor["id"], f"{path}.id")
        if anchor_id in anchor_ids:
            _fail(f"{path}.id", f"duplicate equipment anchor {anchor_id!r}")
        anchor_ids.add(anchor_id)
        if anchor["joint"] not in JOINT_NAMES:
            _fail(f"{path}.joint", "must reference a humanoid joint")

    # Deep-copy the original representation so callers retain stable list ordering.
    return copy.deepcopy(dict(blueprint))


def validate_pose_blueprint_sequence(values: Sequence[Any]) -> tuple[dict[str, Any], ...]:
    """Validate sequence identity and reject duplicate frame or beat data."""

    if isinstance(values, (str, bytes)) or not isinstance(values, Sequence) or not values:
        _fail("$", "must be a non-empty blueprint sequence")
    blueprints = tuple(validate_pose_blueprint(value) for value in values)
    first = blueprints[0]
    identity_fields = ("topology", "direction", "action", "canvas")
    for index, blueprint in enumerate(blueprints[1:], start=1):
        for field in identity_fields:
            if blueprint[field] != first[field]:
                _fail(f"$[{index}].{field}", "must match the first blueprint")

    frame_indices = [item["frame_index"] for item in blueprints]
    if len(frame_indices) != len(set(frame_indices)):
        _fail("$.frame_index", "duplicate frame index")
    if frame_indices != list(range(len(blueprints))):
        _fail("$.frame_index", "must be contiguous and ordered from zero")

    beat_ids = [item["beat_id"] for item in blueprints]
    if len(beat_ids) != len(set(beat_ids)):
        _fail("$.beat_id", "duplicate beat id")
    return blueprints


def _grid_point(x: int, y: int, *, visible: bool = True) -> dict[str, Any]:
    return {"x": x / 31, "y": y / 31, "visible": visible}


def _make_blueprint(
    *,
    action: str,
    beat_id: str,
    frame_index: int,
    points: Mapping[str, tuple[int, int]],
    support: str,
    foot_states: tuple[str, str],
    hand_states: tuple[str, str] = ("open", "open"),
    contact: str = "",
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "topology": HUMANOID_BIPED_TOPOLOGY,
        "direction": "SE",
        "action": action,
        "beat_id": beat_id,
        "frame_index": frame_index,
        "canvas": {"width": 32, "height": 32},
        "joints": [
            {"name": name, **_grid_point(*points[name])} for name in JOINT_NAMES
        ],
        "root": {"x": 16 / 31, "y": 28 / 31},
        "baseline": 28 / 31,
        "support_foot": support,
        "contact_foot": contact or support,
        "hand_state_l": hand_states[0],
        "hand_state_r": hand_states[1],
        "foot_state_l": foot_states[0],
        "foot_state_r": foot_states[1],
        "weapon_contact": {"left": False, "right": False},
        "equipment_anchors": [],
    }


def _idle_points(upper_offset: int, left_hand_y: int, right_hand_y: int) -> dict[str, tuple[int, int]]:
    return {
        "head": (17, 6 + upper_offset),
        "neck": (16, 9 + upper_offset),
        "shoulder_l": (13, 10 + upper_offset),
        "shoulder_r": (19, 10 + upper_offset),
        "elbow_l": (12, 14 + upper_offset),
        "elbow_r": (20, 14 + upper_offset),
        "wrist_l": (12, left_hand_y - 2),
        "wrist_r": (20, right_hand_y - 2),
        "hand_l": (12, left_hand_y),
        "hand_r": (20, right_hand_y),
        "pelvis": (16, 17),
        "hip_l": (14, 18),
        "hip_r": (18, 18),
        "knee_l": (14, 22),
        "knee_r": (18, 22),
        "ankle_l": (14, 26),
        "ankle_r": (18, 26),
        "toe_l": (15, 28),
        "toe_r": (20, 28),
    }


def se_idle_blueprints() -> tuple[dict[str, Any], ...]:
    """Return the four canonical SE idle beats on the generic 32px grid."""

    specs = (
        ("settle", 0, 0, 19, 19),
        ("breathe-up", 1, -1, 18, 18),
        ("settle-return", 2, 0, 18, 19),
        ("breathe-down", 3, 1, 20, 20),
    )
    blueprints = [
        _make_blueprint(
            action="idle",
            beat_id=beat,
            frame_index=index,
            points=_idle_points(offset, left_hand_y, right_hand_y),
            support="both",
            foot_states=("planted", "planted"),
        )
        for beat, index, offset, left_hand_y, right_hand_y in specs
    ]
    return validate_pose_blueprint_sequence(blueprints)


def _walk_points(
    *,
    body_y: int,
    left_leg: tuple[tuple[int, int], tuple[int, int], tuple[int, int], tuple[int, int]],
    right_leg: tuple[tuple[int, int], tuple[int, int], tuple[int, int], tuple[int, int]],
    left_arm: tuple[tuple[int, int], tuple[int, int], tuple[int, int], tuple[int, int]],
    right_arm: tuple[tuple[int, int], tuple[int, int], tuple[int, int], tuple[int, int]],
) -> dict[str, tuple[int, int]]:
    return {
        "head": (17, 6 + body_y),
        "neck": (16, 9 + body_y),
        "shoulder_l": left_arm[0],
        "shoulder_r": right_arm[0],
        "elbow_l": left_arm[1],
        "elbow_r": right_arm[1],
        "wrist_l": left_arm[2],
        "wrist_r": right_arm[2],
        "hand_l": left_arm[3],
        "hand_r": right_arm[3],
        "pelvis": (16, 17 + body_y),
        "hip_l": left_leg[0],
        "hip_r": right_leg[0],
        "knee_l": left_leg[1],
        "knee_r": right_leg[1],
        "ankle_l": left_leg[2],
        "ankle_r": right_leg[2],
        "toe_l": left_leg[3],
        "toe_r": right_leg[3],
    }


def se_walk_blueprints() -> tuple[dict[str, Any], ...]:
    """Return a grounded six-beat SE walk with explicit left/right support."""

    left_arm_back = ((13, 10), (14, 13), (14, 15), (14, 17))
    left_arm_mid = ((13, 11), (12, 15), (12, 17), (12, 19))
    left_arm_front = ((13, 10), (11, 14), (10, 18), (10, 21))
    right_arm_back = ((19, 10), (21, 13), (22, 15), (22, 17))
    right_arm_mid = ((19, 11), (20, 15), (20, 17), (20, 19))
    right_arm_front = ((19, 10), (18, 14), (18, 18), (18, 21))

    specs = (
        (
            "left-contact", 0, 0,
            ((14, 18), (15, 22), (15, 26), (16, 28)),
            ((18, 18), (18, 22), (18, 26), (18, 27)),
            left_arm_mid, right_arm_mid, "left", ("landing", "flight"),
        ),
        (
            "left-down", 1, 1,
            ((14, 19), (14, 23), (12, 27), (11, 28)),
            ((18, 19), (19, 23), (20, 25), (21, 27)),
            left_arm_mid, right_arm_mid, "left", ("planted", "passing"),
        ),
        (
            "left-passing", 2, 0,
            ((14, 18), (15, 22), (16, 26), (16, 28)),
            ((18, 18), (16, 22), (14, 24), (13, 25)),
            left_arm_front, right_arm_back, "left", ("planted", "passing"),
        ),
        (
            "right-contact", 3, 0,
            ((14, 18), (14, 22), (14, 26), (14, 27)),
            ((18, 18), (17, 22), (17, 26), (16, 28)),
            left_arm_mid, right_arm_mid, "right", ("flight", "landing"),
        ),
        (
            "right-down", 4, 1,
            ((14, 19), (13, 23), (12, 25), (11, 27)),
            ((18, 19), (18, 23), (20, 27), (21, 28)),
            left_arm_mid, right_arm_mid, "right", ("passing", "planted"),
        ),
        (
            "right-passing", 5, 0,
            ((14, 18), (16, 22), (18, 24), (19, 25)),
            ((18, 18), (17, 22), (16, 26), (16, 28)),
            left_arm_back, right_arm_front, "right", ("passing", "planted"),
        ),
    )
    blueprints = [
        _make_blueprint(
            action="walk",
            beat_id=beat,
            frame_index=index,
            points=_walk_points(
                body_y=body_y,
                left_leg=left_leg,
                right_leg=right_leg,
                left_arm=left_arm,
                right_arm=right_arm,
            ),
            support=support,
            foot_states=foot_states,
            hand_states=("fist", "fist"),
        )
        for (
            beat,
            index,
            body_y,
            left_leg,
            right_leg,
            left_arm,
            right_arm,
            support,
            foot_states,
        ) in specs
    ]
    return validate_pose_blueprint_sequence(blueprints)


def se_attack_blueprints() -> tuple[dict[str, Any], ...]:
    """Return an unarmed six-beat SE heavy right-punch sequence."""

    stance = {
        "head": (17, 6),
        "neck": (16, 9),
        "shoulder_l": (13, 10),
        "shoulder_r": (19, 10),
        "elbow_l": (14, 13),
        "elbow_r": (19, 13),
        "wrist_l": (15, 15),
        "wrist_r": (18, 15),
        "hand_l": (16, 16),
        "hand_r": (18, 17),
        "pelvis": (16, 17),
        "hip_l": (14, 18),
        "hip_r": (18, 18),
        "knee_l": (13, 22),
        "knee_r": (19, 22),
        "ankle_l": (12, 26),
        "ankle_r": (21, 26),
        "toe_l": (12, 28),
        "toe_r": (22, 28),
    }
    specs = (
        ("ready", {}),
        (
            "anticipation",
            {
                "head": (16, 6), "neck": (15, 9),
                "shoulder_l": (12, 11), "shoulder_r": (18, 10),
                "elbow_l": (14, 14), "wrist_l": (15, 16), "hand_l": (16, 17),
                "elbow_r": (21, 12), "wrist_r": (20, 14), "hand_r": (19, 15),
                "pelvis": (15, 17), "hip_l": (13, 18), "hip_r": (18, 18),
            },
        ),
        (
            "wind-up",
            {
                "head": (16, 6), "neck": (15, 9),
                "shoulder_l": (13, 11), "shoulder_r": (18, 9),
                "elbow_l": (14, 14), "wrist_l": (16, 15), "hand_l": (17, 16),
                "elbow_r": (20, 10), "wrist_r": (18, 12), "hand_r": (17, 14),
                "pelvis": (15, 17), "hip_l": (13, 18), "hip_r": (18, 18),
            },
        ),
        (
            "strike",
            {
                "head": (18, 7), "neck": (17, 10),
                "shoulder_l": (13, 12), "shoulder_r": (20, 10),
                "elbow_l": (14, 15), "wrist_l": (16, 16), "hand_l": (17, 17),
                "elbow_r": (23, 12), "wrist_r": (25, 14), "hand_r": (27, 16),
                "pelvis": (17, 18), "hip_l": (14, 19), "hip_r": (19, 19),
                "knee_l": (13, 23), "knee_r": (20, 23),
            },
        ),
        (
            "impact",
            {
                "head": (19, 7), "neck": (18, 10),
                "shoulder_l": (13, 13), "shoulder_r": (21, 10),
                "elbow_l": (14, 16), "wrist_l": (16, 17), "hand_l": (17, 18),
                "elbow_r": (24, 12), "wrist_r": (27, 14), "hand_r": (29, 16),
                "pelvis": (17, 18), "hip_l": (14, 19), "hip_r": (19, 19),
                "knee_l": (13, 23), "knee_r": (20, 23),
            },
        ),
        (
            "recovery",
            {
                "head": (18, 6), "neck": (17, 9),
                "shoulder_l": (13, 11), "shoulder_r": (19, 10),
                "elbow_l": (14, 14), "wrist_l": (15, 16), "hand_l": (16, 17),
                "elbow_r": (21, 13), "wrist_r": (20, 16), "hand_r": (19, 17),
                "pelvis": (16, 17), "hip_l": (14, 18), "hip_r": (18, 18),
            },
        ),
    )
    blueprints = [
        _make_blueprint(
            action="attack",
            beat_id=beat,
            frame_index=index,
            points={**stance, **updates},
            support="left",
            contact="both",
            foot_states=("planted", "planted"),
            hand_states=("fist", "fist"),
        )
        for index, (beat, updates) in enumerate(specs)
    ]
    return validate_pose_blueprint_sequence(blueprints)


def _pixel(point: Mapping[str, Any], width: int, height: int) -> tuple[int, int]:
    return round(point["x"] * (width - 1)), round(point["y"] * (height - 1))


def render_pose_blueprint_png(value: Any, *, scale: int = 8) -> bytes:
    """Render on the target pixel grid, then upscale only with nearest-neighbor."""

    blueprint = validate_pose_blueprint(value)
    if type(scale) is not int or not 1 <= scale <= 64:
        raise PoseBlueprintError("scale: must be an integer in 1..64")

    width = blueprint["canvas"]["width"]
    height = blueprint["canvas"]["height"]
    image = Image.new("RGBA", (width, height), (9, 12, 20, 255))
    draw = ImageDraw.Draw(image)
    joints = {joint["name"]: joint for joint in blueprint["joints"]}

    baseline_y = round(blueprint["baseline"] * (height - 1))
    draw.line((0, baseline_y, width - 1, baseline_y), fill=(45, 75, 92, 255))

    left_color = (244, 118, 74, 255)
    right_color = (64, 164, 255, 255)
    center_color = (244, 211, 94, 255)
    upper_edges = (
        ("head", "neck", center_color),
        ("neck", "shoulder_l", left_color),
        ("shoulder_l", "elbow_l", left_color),
        ("elbow_l", "wrist_l", left_color),
        ("wrist_l", "hand_l", left_color),
        ("neck", "shoulder_r", right_color),
        ("shoulder_r", "elbow_r", right_color),
        ("elbow_r", "wrist_r", right_color),
        ("wrist_r", "hand_r", right_color),
        ("neck", "pelvis", center_color),
    )
    leg_edges = {
        "left": (
            ("pelvis", "hip_l", left_color),
            ("hip_l", "knee_l", left_color),
            ("knee_l", "ankle_l", left_color),
            ("ankle_l", "toe_l", left_color),
        ),
        "right": (
            ("pelvis", "hip_r", right_color),
            ("hip_r", "knee_r", right_color),
            ("knee_r", "ankle_r", right_color),
            ("ankle_r", "toe_r", right_color),
        ),
    }
    # Draw the planted leg first and the passing/flight leg last so the guide
    # itself communicates which limb crosses in front at the overlap.
    leg_order = ("right", "left") if blueprint["support_foot"] == "right" else ("left", "right")
    edges = upper_edges + tuple(
        edge for side in leg_order for edge in leg_edges[side]
    )
    for start, end, color in edges:
        if joints[start]["visible"] and joints[end]["visible"]:
            draw.line(
                (*_pixel(joints[start], width, height), *_pixel(joints[end], width, height)),
                fill=color,
                width=2,
            )

    torso = [
        _pixel(joints[name], width, height)
        for name in ("shoulder_l", "shoulder_r", "hip_r", "hip_l")
    ]
    draw.polygon(torso, fill=(91, 78, 44, 255), outline=center_color)
    head_x, head_y = _pixel(joints["head"], width, height)
    draw.ellipse((head_x - 2, head_y - 2, head_x + 2, head_y + 2), fill=center_color)

    for name, color in (
        ("hand_l", left_color),
        ("hand_r", right_color),
        ("toe_l", left_color),
        ("toe_r", right_color),
    ):
        if joints[name]["visible"]:
            x, y = _pixel(joints[name], width, height)
            draw.rectangle((x - 1, y - 1, x + 1, y + 1), fill=color)

    root_x, root_y = _pixel(blueprint["root"], width, height)
    draw.line((root_x - 1, root_y, root_x + 1, root_y), fill=(255, 72, 196, 255))
    draw.line((root_x, root_y - 1, root_x, root_y + 1), fill=(255, 72, 196, 255))

    if scale != 1:
        image = image.resize((width * scale, height * scale), Image.Resampling.NEAREST)
    output = io.BytesIO()
    image.save(output, format="PNG", optimize=False, compress_level=9)
    return output.getvalue()


def render_pose_blueprint_prompt_png(value: Any) -> bytes:
    """Add unambiguous screen-space phase labels to the clean 512px pose guide."""
    blueprint = validate_pose_blueprint(value)
    image = Image.open(
        io.BytesIO(render_pose_blueprint_png(blueprint, scale=16))
    ).convert("RGBA")
    draw = ImageDraw.Draw(image)
    try:
        font = ImageFont.load_default(size=18)
    except TypeError:  # Pillow versions before the sized default font.
        font = ImageFont.load_default()
    joints = {joint["name"]: joint for joint in blueprint["joints"]}

    def point(name: str) -> tuple[int, int]:
        joint = joints[name]
        return round(joint["x"] * 511), round(joint["y"] * 511)

    draw.rectangle((8, 8, 504, 42), fill=(0, 0, 0, 220))
    draw.text((18, 15), "POSE ONLY - SE WALK - SCREEN COORDINATES", fill=(255, 255, 255, 255), font=font)
    phase_label = "NEUTRAL TRANSITION - FEET CLOSE"
    swing_name = None
    support_name = f"toe_{blueprint['support_foot'][0]}"
    if blueprint["beat_id"] == "left-passing":
        phase_label = "BLUE SWING BOOT -> SCREEN-LEFT FRONT | ORANGE HAND DOWN"
        swing_name = "toe_r"
    elif blueprint["beat_id"] == "right-passing":
        phase_label = "ORANGE SWING BOOT -> SCREEN-RIGHT FRONT | BLUE HAND DOWN"
        swing_name = "toe_l"
    draw.rectangle((8, 468, 504, 504), fill=(0, 0, 0, 220))
    draw.text((18, 477), phase_label, fill=(255, 255, 255, 255), font=font)

    support_x, support_y = point(support_name)
    draw.ellipse(
        (support_x - 18, support_y - 18, support_x + 18, support_y + 18),
        outline=(80, 255, 130, 255),
        width=6,
    )
    if swing_name is not None:
        swing_x, swing_y = point(swing_name)
        draw.ellipse(
            (swing_x - 24, swing_y - 24, swing_x + 24, swing_y + 24),
            outline=(255, 255, 255, 255),
            width=7,
        )
        direction = -1 if blueprint["beat_id"] == "left-passing" else 1
        arrow_start = (swing_x - direction * 70, swing_y - 42)
        arrow_end = (swing_x, swing_y - 8)
        draw.line((*arrow_start, *arrow_end), fill=(255, 255, 255, 255), width=7)
        draw.polygon(
            (
                arrow_end,
                (arrow_end[0] - direction * 18, arrow_end[1] - 13),
                (arrow_end[0] - direction * 18, arrow_end[1] + 13),
            ),
            fill=(255, 255, 255, 255),
        )
    output = io.BytesIO()
    image.save(output, format="PNG", optimize=False, compress_level=9)
    return output.getvalue()
