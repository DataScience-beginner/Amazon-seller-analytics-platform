from __future__ import annotations

import json
import re
from collections import defaultdict
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path
from typing import Final, cast

from app.modules.imports.domain import CanonicalField, CanonicalValueType
from app.modules.imports.normalization import normalize_header

_IDENTIFIER_PATTERN: Final = re.compile(r"^[a-z][a-z0-9_]{0,127}$")
_VERSION_PATTERN: Final = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
_TOP_LEVEL_KEYS: Final = {"schema_version", "registry_id", "version", "fields"}
_FIELD_KEYS: Final = {"canonical_field", "required", "value_type", "aliases", "description"}


class RegistryValidationError(ValueError):
    """Raised when an alias manifest is not safe to load."""


@dataclass(frozen=True, slots=True)
class AliasRegistry:
    registry_id: str
    version: str
    fields: tuple[CanonicalField, ...]

    @classmethod
    def default(cls) -> AliasRegistry:
        resource = files("app.modules.imports").joinpath("resources/keepa_aliases.v1.json")
        return cls.from_json(resource.read_text(encoding="utf-8"))

    @classmethod
    def from_path(cls, path: Path) -> AliasRegistry:
        return cls.from_json(path.read_text(encoding="utf-8"))

    @classmethod
    def from_json(cls, manifest: str) -> AliasRegistry:
        try:
            payload: object = json.loads(manifest)
        except json.JSONDecodeError as exc:
            raise RegistryValidationError("Alias manifest is not valid JSON") from exc
        return cls.from_object(payload)

    @classmethod
    def from_object(cls, payload: object) -> AliasRegistry:
        root = _require_string_key_dict(payload, "manifest")
        _reject_unknown_keys(root, _TOP_LEVEL_KEYS, "manifest")

        schema_version = root.get("schema_version")
        if type(schema_version) is not int or schema_version != 1:
            raise RegistryValidationError("schema_version must be the integer 1")

        registry_id = _require_nonempty_string(root.get("registry_id"), "registry_id")
        if _IDENTIFIER_PATTERN.fullmatch(registry_id) is None:
            raise RegistryValidationError("registry_id must be a lower snake-case identifier")

        version = _require_nonempty_string(root.get("version"), "version")
        if _VERSION_PATTERN.fullmatch(version) is None:
            raise RegistryValidationError("version contains unsupported characters")

        raw_fields = root.get("fields")
        if not isinstance(raw_fields, list) or not raw_fields:
            raise RegistryValidationError("fields must be a non-empty array")

        canonical_fields: list[CanonicalField] = []
        seen_names: set[str] = set()
        for position, raw_field in enumerate(raw_fields, start=1):
            context = f"fields[{position}]"
            item = _require_string_key_dict(raw_field, context)
            _reject_unknown_keys(item, _FIELD_KEYS, context)

            name = _require_nonempty_string(
                item.get("canonical_field"), f"{context}.canonical_field"
            )
            if _IDENTIFIER_PATTERN.fullmatch(name) is None:
                raise RegistryValidationError(
                    f"{context}.canonical_field must be a lower snake-case identifier"
                )
            if name in seen_names:
                raise RegistryValidationError(f"Duplicate canonical field: {name}")
            seen_names.add(name)

            required = item.get("required")
            if type(required) is not bool:
                raise RegistryValidationError(f"{context}.required must be a boolean")

            raw_value_type = _require_nonempty_string(
                item.get("value_type"), f"{context}.value_type"
            )
            try:
                value_type = CanonicalValueType(raw_value_type)
            except ValueError as exc:
                allowed = ", ".join(value.value for value in CanonicalValueType)
                raise RegistryValidationError(
                    f"{context}.value_type must be one of: {allowed}"
                ) from exc

            raw_aliases = item.get("aliases")
            if not isinstance(raw_aliases, list) or not raw_aliases:
                raise RegistryValidationError(f"{context}.aliases must be a non-empty array")
            aliases: list[str] = []
            normalized_aliases: set[str] = set()
            for alias_position, raw_alias in enumerate(raw_aliases, start=1):
                alias = _require_nonempty_string(raw_alias, f"{context}.aliases[{alias_position}]")
                normalized_alias = normalize_header(alias)
                if not normalized_alias:
                    raise RegistryValidationError(
                        f"{context}.aliases[{alias_position}] normalizes to an empty value"
                    )
                if normalized_alias in normalized_aliases:
                    raise RegistryValidationError(
                        f"{context} contains duplicate aliases after normalization"
                    )
                normalized_aliases.add(normalized_alias)
                aliases.append(alias)

            description = _require_nonempty_string(
                item.get("description"), f"{context}.description"
            )
            canonical_fields.append(
                CanonicalField(
                    name=name,
                    required=required,
                    value_type=value_type,
                    aliases=tuple(aliases),
                    description=description,
                )
            )

        return cls(registry_id=registry_id, version=version, fields=tuple(canonical_fields))

    @property
    def fields_by_name(self) -> dict[str, CanonicalField]:
        return {field.name: field for field in self.fields}

    @property
    def alias_index(self) -> dict[str, tuple[str, ...]]:
        index: defaultdict[str, list[str]] = defaultdict(list)
        for field in self.fields:
            aliases = (*field.aliases, field.name)
            for alias in aliases:
                normalized_alias = normalize_header(alias)
                if field.name not in index[normalized_alias]:
                    index[normalized_alias].append(field.name)
        return {alias: tuple(sorted(names)) for alias, names in index.items()}

    def candidates_for(self, normalized_header: str) -> tuple[str, ...]:
        if not normalized_header:
            return ()
        return self.alias_index.get(normalized_header, ())

    def get_field(self, name: str) -> CanonicalField:
        try:
            return self.fields_by_name[name]
        except KeyError as exc:
            raise RegistryValidationError(f"Unknown canonical field: {name}") from exc


def _require_string_key_dict(value: object, context: str) -> dict[str, object]:
    if not isinstance(value, dict) or any(not isinstance(key, str) for key in value):
        raise RegistryValidationError(f"{context} must be an object with string keys")
    return cast(dict[str, object], value)


def _require_nonempty_string(value: object, context: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise RegistryValidationError(f"{context} must be a non-empty string")
    return value.strip()


def _reject_unknown_keys(payload: dict[str, object], allowed: set[str], context: str) -> None:
    unknown = sorted(set(payload) - allowed)
    if unknown:
        raise RegistryValidationError(f"{context} contains unknown keys: {', '.join(unknown)}")
