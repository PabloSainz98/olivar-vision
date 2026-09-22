"""Offline validation for the dataset source inventory."""

import json
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Dict, Iterable, List
from urllib.parse import urlparse


ALLOWED_STATUSES = {
    "APTO_PARA_AUDITORIA",
    "PENDIENTE_DE_LICENCIA",
    "PENDIENTE_DE_ACCESO",
    "FUERA_DE_DOMINIO",
}

ALLOWED_CAPTURE_TYPES = {
    "terrestrial_leaf_closeup",
    "terrestrial_field_leaf",
    "terrestrial_leaf_controlled_capture",
    "processed_or_augmented_leaf_image",
    "uav_rgb",
}

LICENSE_STATUSES = {
    "VERIFIED_DECLARED",
    "DECLARED_BY_MIRROR_OR_THIRD_PARTY",
    "MISSING_OR_UNVERIFIED",
}

SOURCE_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_]*[a-z0-9]$")


class ManifestError(ValueError):
    """Raised when a dataset manifest is incomplete or inconsistent."""


@dataclass(frozen=True)
class ValidationResult:
    source_count: int
    apt_for_audit_count: int


def load_manifest(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def validate_manifest(manifest: Dict[str, Any]) -> ValidationResult:
    _require(isinstance(manifest, dict), "manifest must be a JSON object")
    _require(manifest.get("schema_version") == 1, "schema_version must be 1")
    _require_nonempty_string(manifest.get("project"), "project")
    _require_date(manifest.get("updated_at"), "updated_at")
    _require_date(manifest.get("consulted_at"), "consulted_at")

    sources = manifest.get("sources")
    _require(isinstance(sources, list) and sources, "sources must be a non-empty list")

    ids = [_source_id(source, index) for index, source in enumerate(sources)]
    duplicates = sorted({source_id for source_id in ids if ids.count(source_id) > 1})
    _require(not duplicates, "duplicate source id(s): " + ", ".join(duplicates))
    known_ids = set(ids)

    apt_count = 0
    for source in sources:
        if _validate_source(source, known_ids):
            apt_count += 1

    return ValidationResult(source_count=len(sources), apt_for_audit_count=apt_count)


def validate_manifest_file(path: Path) -> ValidationResult:
    return validate_manifest(load_manifest(path))


def _validate_source(source: Dict[str, Any], known_ids: Iterable[str]) -> bool:
    _require(isinstance(source, dict), "each source must be an object")
    source_id = _source_id(source, 0)

    for field in ("name", "publisher", "source_type", "status_justification"):
        _require_nonempty_string(source.get(field), f"{source_id}.{field}")

    status = source.get("status")
    _require(status in ALLOWED_STATUSES, f"{source_id}.status is not allowed: {status}")

    urls = source.get("urls")
    _require(isinstance(urls, list) and urls, f"{source_id}.urls must be non-empty")
    for url_item in urls:
        _require(isinstance(url_item, dict), f"{source_id}.urls entries must be objects")
        _require_nonempty_string(url_item.get("label"), f"{source_id}.urls.label")
        _require_valid_url(url_item.get("url"), f"{source_id}.urls.url")

    license_info = source.get("license")
    _require(isinstance(license_info, dict), f"{source_id}.license must be an object")
    _require_nonempty_string(license_info.get("declared"), f"{source_id}.license.declared")
    license_status = license_info.get("status")
    _require(
        license_status in LICENSE_STATUSES,
        f"{source_id}.license.status is not allowed: {license_status}",
    )
    evidence_urls = license_info.get("evidence_urls")
    _require(
        isinstance(evidence_urls, list) and evidence_urls,
        f"{source_id}.license.evidence_urls must be non-empty",
    )
    for url in evidence_urls:
        _require_valid_url(url, f"{source_id}.license.evidence_urls")
    _require_nonempty_string(
        license_info.get("evidence_summary"),
        f"{source_id}.license.evidence_summary",
    )

    declared_content = source.get("declared_content")
    _require(
        isinstance(declared_content, dict),
        f"{source_id}.declared_content must be an object",
    )
    capture_types = declared_content.get("capture_types")
    _require(
        isinstance(capture_types, list) and capture_types,
        f"{source_id}.declared_content.capture_types must be non-empty",
    )
    invalid_capture_types = sorted(set(capture_types) - ALLOWED_CAPTURE_TYPES)
    _require(
        not invalid_capture_types,
        f"{source_id}.declared_content.capture_types has unknown value(s): "
        + ", ".join(invalid_capture_types),
    )
    task_types = declared_content.get("task_types")
    _require(
        isinstance(task_types, list) and task_types,
        f"{source_id}.declared_content.task_types must be non-empty",
    )
    classes = declared_content.get("declared_classes")
    _require(
        isinstance(classes, list) and classes,
        f"{source_id}.declared_content.declared_classes must be non-empty",
    )
    _require(
        isinstance(declared_content.get("declared_total_images_verified"), bool),
        f"{source_id}.declared_content.declared_total_images_verified must be boolean",
    )

    access = source.get("access")
    _require(isinstance(access, dict), f"{source_id}.access must be an object")
    _require_nonempty_string(access.get("access_status"), f"{source_id}.access.access_status")
    _require(
        access.get("downloaded_in_phase_1") is False,
        f"{source_id}.access.downloaded_in_phase_1 must remain false in phase 1",
    )

    relationships = source.get("relationships", [])
    _require(isinstance(relationships, list), f"{source_id}.relationships must be a list")
    for relationship in relationships:
        _require(
            isinstance(relationship, dict),
            f"{source_id}.relationships entries must be objects",
        )
        target_id = relationship.get("target_id")
        if target_id is not None:
            _require(target_id in known_ids, f"{source_id}.relationships target not found: {target_id}")
        _require_nonempty_string(relationship.get("type"), f"{source_id}.relationships.type")
        _require_nonempty_string(relationship.get("evidence"), f"{source_id}.relationships.evidence")

    if status == "APTO_PARA_AUDITORIA":
        _require(
            license_status == "VERIFIED_DECLARED",
            f"{source_id} is APTO_PARA_AUDITORIA but license is not verified",
        )
        _require(
            license_info.get("spdx"),
            f"{source_id} is APTO_PARA_AUDITORIA but license.spdx is missing",
        )

    return status == "APTO_PARA_AUDITORIA"


def _source_id(source: Dict[str, Any], index: int) -> str:
    _require(isinstance(source, dict), f"sources[{index}] must be an object")
    source_id = source.get("id")
    _require_nonempty_string(source_id, f"sources[{index}].id")
    _require(SOURCE_ID_RE.match(source_id), f"invalid source id: {source_id}")
    return source_id


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ManifestError(message)


def _require_nonempty_string(value: Any, field: str) -> None:
    _require(isinstance(value, str) and value.strip(), f"{field} must be a non-empty string")


def _require_valid_url(value: Any, field: str) -> None:
    _require_nonempty_string(value, field)
    parsed = urlparse(value)
    _require(parsed.scheme in {"http", "https"} and bool(parsed.netloc), f"{field} is not a valid http(s) URL: {value}")


def _require_date(value: Any, field: str) -> None:
    _require_nonempty_string(value, field)
    try:
        date.fromisoformat(value)
    except ValueError as exc:
        raise ManifestError(f"{field} must be YYYY-MM-DD: {value}") from exc

