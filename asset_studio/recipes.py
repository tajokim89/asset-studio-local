from __future__ import annotations

import copy
import json
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Optional, Union


SCHEMA_VERSION = "asset-studio.asset-recipes/v1"
QUALITY_RUBRIC_VERSION = "quality-rubric-v1"
DEFAULT_REGISTRY_PATH = (
    Path(__file__).resolve().parents[1] / "contracts" / "asset-recipes.json"
)

_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_REQUIRED_STAGES = (
    "generate",
    "local_qa",
    "visual_qa",
    "user_approval",
    "edit",
    "export",
)
_TOP_LEVEL_KEYS = {
    "schema_version",
    "quality_rubric_version",
    "recipes",
    "legacy_subtypes",
}
_RECIPE_KEYS = {
    "id",
    "title",
    "description",
    "channel",
    "readiness",
    "family",
    "transport",
    "generation_strategy",
    "reference_policy",
    "default_output_profile_id",
    "export_capability",
    "golden_job_ids",
    "required_stages",
}
_EXPORT_CAPABILITY_KEYS = {"route", "options"}
_LEGACY_KEYS = {
    "legacy_id",
    "family",
    "type",
    "classification",
    "recipe_id",
    "variant",
    "migration_action",
    "reason",
}
_CLASSIFICATION_ACTIONS = {
    "production": "use_recipe",
    "alias": "normalize_alias",
    "lab": "keep_lab",
    "retired": "remove",
}


class RecipeRegistryError(ValueError):
    """Raised when the asset recipe registry violates its v1 contract."""


def _fail(path: str, message: str) -> None:
    raise RecipeRegistryError(f"{path}: {message}")


def _strict_object(value: Any, path: str, keys: set[str]) -> Mapping:
    if not isinstance(value, Mapping):
        _fail(path, "must be an object")
    actual = set(value)
    if actual != keys:
        details = []
        missing = sorted(keys - actual)
        unknown = sorted(actual - keys)
        if missing:
            details.append(f"missing {missing}")
        if unknown:
            details.append(f"unknown {unknown}")
        _fail(path, "; ".join(details))
    return value


def _string(value: Any, path: str, maximum: int = 4096) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        _fail(path, f"must be a non-empty string of at most {maximum} characters")
    return value


def _identifier(value: Any, path: str) -> str:
    value = _string(value, path, 128)
    if not _IDENTIFIER.fullmatch(value):
        _fail(path, "must be a portable identifier")
    return value


def _enum(value: Any, path: str, choices: set[str]) -> str:
    if value not in choices:
        _fail(path, f"must be one of {sorted(choices)}")
    return value


def _identifier_list(value: Any, path: str) -> list[str]:
    if not isinstance(value, list):
        _fail(path, "must be an array")
    result = []
    for index, item in enumerate(value):
        result.append(_identifier(item, f"{path}[{index}]"))
    if len(set(result)) != len(result):
        _fail(path, "must not contain duplicate identifiers")
    return result


def validate_recipe_registry(data: Any) -> dict[str, Any]:
    """Validate a v1 registry and return a detached copy."""

    registry = _strict_object(data, "$", _TOP_LEVEL_KEYS)
    if registry["schema_version"] != SCHEMA_VERSION:
        _fail("$.schema_version", f"must equal {SCHEMA_VERSION!r}")
    if registry["quality_rubric_version"] != QUALITY_RUBRIC_VERSION:
        _fail(
            "$.quality_rubric_version",
            f"must equal {QUALITY_RUBRIC_VERSION!r}",
        )

    recipes = registry["recipes"]
    if not isinstance(recipes, list) or not recipes:
        _fail("$.recipes", "must be a non-empty array")

    recipe_ids = set()
    recipes_by_id = {}
    transport_keys = set()
    golden_job_ids = set()
    for index, raw_recipe in enumerate(recipes):
        path = f"$.recipes[{index}]"
        recipe = _strict_object(raw_recipe, path, _RECIPE_KEYS)
        recipe_id = _identifier(recipe["id"], f"{path}.id")
        if recipe_id in recipe_ids:
            _fail(f"{path}.id", "must be unique")
        recipe_ids.add(recipe_id)
        recipes_by_id[recipe_id] = recipe

        _string(recipe["title"], f"{path}.title", 256)
        _string(recipe["description"], f"{path}.description")
        channel = _enum(
            recipe["channel"], f"{path}.channel", {"production", "lab"}
        )
        readiness = _enum(
            recipe["readiness"],
            f"{path}.readiness",
            {"contract_only", "ready"},
        )
        family = _identifier(recipe["family"], f"{path}.family")

        transport = _strict_object(
            recipe["transport"], f"{path}.transport", {"family", "type"}
        )
        transport_key = (
            _identifier(transport["family"], f"{path}.transport.family"),
            _identifier(transport["type"], f"{path}.transport.type"),
        )
        if transport_key in transport_keys:
            _fail(f"{path}.transport", "family/type must be unique")
        transport_keys.add(transport_key)

        _identifier(
            recipe["generation_strategy"], f"{path}.generation_strategy"
        )
        _enum(
            recipe["reference_policy"],
            f"{path}.reference_policy",
            {"none", "optional", "identity_master"},
        )
        profile_id = recipe["default_output_profile_id"]
        if profile_id is not None:
            _identifier(profile_id, f"{path}.default_output_profile_id")
        elif readiness == "ready":
            _fail(
                f"{path}.default_output_profile_id",
                "ready recipes require a resolved output profile",
            )
        capability = _strict_object(
            recipe["export_capability"],
            f"{path}.export_capability",
            _EXPORT_CAPABILITY_KEYS,
        )
        route = _enum(
            capability["route"],
            f"{path}.export_capability.route",
            {"actor", "effect", "tile", "ui", "object"},
        )
        if route != family:
            _fail(
                f"{path}.export_capability.route",
                "must equal the recipe family",
            )
        options = _identifier_list(
            capability["options"], f"{path}.export_capability.options"
        )
        if not options:
            _fail(f"{path}.export_capability.options", "must not be empty")
        jobs = _identifier_list(recipe["golden_job_ids"], f"{path}.golden_job_ids")
        for job_id in jobs:
            if job_id in golden_job_ids:
                _fail(f"{path}.golden_job_ids", f"duplicate global job id {job_id!r}")
            golden_job_ids.add(job_id)
        if channel == "production" and not jobs:
            _fail(f"{path}.golden_job_ids", "production recipes require a golden job")

        stages = recipe["required_stages"]
        if not isinstance(stages, list) or tuple(stages) != _REQUIRED_STAGES:
            _fail(
                f"{path}.required_stages",
                f"must equal {list(_REQUIRED_STAGES)!r}",
            )

    legacy_subtypes = registry["legacy_subtypes"]
    if not isinstance(legacy_subtypes, list):
        _fail("$.legacy_subtypes", "must be an array")

    legacy_ids = set()
    legacy_keys = set()
    canonical_production_recipe_ids = set()
    for index, raw_legacy in enumerate(legacy_subtypes):
        path = f"$.legacy_subtypes[{index}]"
        legacy = _strict_object(raw_legacy, path, _LEGACY_KEYS)
        family = _identifier(legacy["family"], f"{path}.family")
        subtype = _identifier(legacy["type"], f"{path}.type")
        legacy_id = _identifier(legacy["legacy_id"], f"{path}.legacy_id")
        if legacy_id != f"{family}.{subtype}":
            _fail(f"{path}.legacy_id", "must equal family + '.' + type")
        if legacy_id in legacy_ids:
            _fail(f"{path}.legacy_id", "must be unique")
        legacy_ids.add(legacy_id)
        if (family, subtype) in legacy_keys:
            _fail(path, "family/type must be unique")
        legacy_keys.add((family, subtype))

        classification = _enum(
            legacy["classification"],
            f"{path}.classification",
            set(_CLASSIFICATION_ACTIONS),
        )
        expected_action = _CLASSIFICATION_ACTIONS[classification]
        if legacy["migration_action"] != expected_action:
            _fail(
                f"{path}.migration_action",
                f"must equal {expected_action!r} for {classification!r}",
            )

        recipe_id = legacy["recipe_id"]
        recipe = None
        if recipe_id is not None:
            recipe_id = _identifier(recipe_id, f"{path}.recipe_id")
            if recipe_id not in recipe_ids:
                _fail(f"{path}.recipe_id", "must reference an existing recipe")
            recipe = recipes_by_id[recipe_id]
        elif classification in {"production", "alias"}:
            _fail(
                f"{path}.recipe_id",
                f"is required for {classification!r} entries",
            )

        variant = legacy["variant"]
        if variant is not None:
            _identifier(variant, f"{path}.variant")
        elif classification in {"production", "alias"}:
            _fail(f"{path}.variant", f"is required for {classification!r} entries")

        if classification in {"production", "alias"}:
            if recipe["channel"] != "production":
                _fail(f"{path}.recipe_id", "must reference a production recipe")
            if recipe["transport"]["family"] != family:
                _fail(
                    f"{path}.recipe_id",
                    "must reference a recipe in the same transport family",
                )
            if classification == "production":
                if recipe["transport"] != {"family": family, "type": subtype}:
                    _fail(
                        path,
                        "production entry must equal its recipe canonical transport",
                    )
                canonical_production_recipe_ids.add(recipe_id)
        elif classification == "lab" and recipe is not None:
            if recipe["channel"] != "lab":
                _fail(f"{path}.recipe_id", "must reference a Lab recipe")
            if recipe["transport"]["family"] != family:
                _fail(
                    f"{path}.recipe_id",
                    "must reference a recipe in the same transport family",
                )
        elif classification == "retired" and (recipe_id is not None or variant is not None):
            _fail(path, "retired entries must not reference a recipe or variant")
        _string(legacy["reason"], f"{path}.reason", 1024)

    production_recipe_ids = {
        recipe_id
        for recipe_id, recipe in recipes_by_id.items()
        if recipe["channel"] == "production"
    }
    missing_canonical = production_recipe_ids - canonical_production_recipe_ids
    if missing_canonical:
        _fail(
            "$.legacy_subtypes",
            f"missing canonical production entries for {sorted(missing_canonical)}",
        )

    return copy.deepcopy(dict(registry))


def load_recipe_registry(
    path: Optional[Union[str, Path]] = None,
) -> dict[str, Any]:
    """Read and validate a registry from the default or injected path."""

    registry_path = DEFAULT_REGISTRY_PATH if path is None else Path(path)
    try:
        data = json.loads(registry_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise RecipeRegistryError(f"{registry_path}: cannot load registry ({exc})") from exc
    return validate_recipe_registry(data)


def recipe_by_id(registry: Mapping, recipe_id: str) -> Optional[dict]:
    """Return a recipe by exact id, or None when it is absent."""

    for recipe in registry.get("recipes", []):
        if recipe.get("id") == recipe_id:
            return recipe
    return None


def legacy_by_key(
    registry: Mapping, family: str, subtype: str
) -> Optional[dict]:
    """Return a legacy mapping by exact family/type, or None when absent."""

    for legacy in registry.get("legacy_subtypes", []):
        if legacy.get("family") == family and legacy.get("type") == subtype:
            return legacy
    return None


def migrate_legacy_selection(
    registry: Mapping, family: str, subtype: str
) -> dict[str, Any]:
    """Resolve one legacy selection without promoting Lab entries."""

    legacy = legacy_by_key(registry, family, subtype)
    if legacy is None:
        raise RecipeRegistryError(
            f"unknown legacy asset selection {family!r}/{subtype!r}"
        )
    classification = legacy["classification"]
    if classification == "retired":
        raise RecipeRegistryError(
            f"retired legacy asset selection {family!r}/{subtype!r}"
        )

    recipe_id = legacy["recipe_id"]
    recipe = recipe_by_id(registry, recipe_id) if recipe_id is not None else None
    if recipe_id is not None and recipe is None:
        raise RecipeRegistryError(
            f"legacy asset selection {family!r}/{subtype!r} references "
            f"unknown recipe {recipe_id!r}"
        )

    if classification in {"production", "alias"}:
        if recipe is None or recipe["channel"] != "production":
            raise RecipeRegistryError(
                f"{classification} legacy asset selection {family!r}/{subtype!r} "
                "requires a production recipe"
            )
        transport = recipe["transport"]
        channel = "production"
    else:
        transport = (
            recipe["transport"]
            if recipe is not None
            else {"family": family, "type": subtype}
        )
        channel = "lab"

    return {
        "classification": classification,
        "channel": channel,
        "recipe_id": recipe_id,
        "transport": copy.deepcopy(transport),
        "variant": legacy["variant"],
    }
