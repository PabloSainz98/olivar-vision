"""Offline, read-only image inventory and split-leakage audit."""

import hashlib
import json
import os
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from olivar_vision.dataset_manifest import load_manifest, validate_manifest
from olivar_vision.image_fingerprint import ImageDecodeError, decode_image, dhash64, hamming_distance


ENGINE_NAME = "olivar-vision-data-audit"
ENGINE_VERSION = "1.0.0"
PERCEPTUAL_ALGORITHM = "dhash64-luma-nearest-v1"
ROOT_ENV_RE = re.compile(r"^OLIVAR_[A-Z0-9_]+_ROOT$")
EXPECTED_FORMAT_BY_EXTENSION = {
    ".bmp": {"BMP"},
    ".heic": {"HEIC", "HEIF"},
    ".jpeg": {"JPEG"},
    ".jpg": {"JPEG"},
    ".pgm": {"PGM"},
    ".png": {"PNG"},
    ".ppm": {"PPM"},
    ".tif": {"TIFF"},
    ".tiff": {"TIFF"},
    ".webp": {"WEBP"},
}


class AuditError(ValueError):
    """Raised for invalid configuration or an unsafe/unusable input."""


class NoDataError(AuditError):
    """Raised when no local files exist to audit."""


@dataclass(frozen=True)
class SourceAuditSpec:
    source_id: str
    version: str
    root_env: str
    splits: Mapping[str, str]
    allowed_labels: Tuple[str, ...]
    extensions: Tuple[str, ...]
    manual_review_status: str
    group_identifiers: Mapping[str, bool]


@dataclass(frozen=True)
class AuditConfig:
    audit_id: str
    audit_date: str
    perceptual_distance_threshold: int
    manual_review_sample_size_per_label: int
    sources: Tuple[SourceAuditSpec, ...]


def load_audit_config(path: Path, manifest_path: Path) -> Tuple[AuditConfig, Dict[str, Any]]:
    try:
        raw_config = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AuditError(f"cannot read audit config: {exc}") from exc
    try:
        manifest = load_manifest(manifest_path)
        validate_manifest(manifest)
    except (OSError, ValueError) as exc:
        raise AuditError(f"dataset manifest is invalid: {exc}") from exc
    return validate_audit_config(raw_config, manifest), manifest


def validate_audit_config(config: Dict[str, Any], manifest: Dict[str, Any]) -> AuditConfig:
    _require(isinstance(config, dict), "audit config must be an object")
    _require(config.get("schema_version") == 1, "audit config schema_version must be 1")
    audit_id = _required_string(config.get("audit_id"), "audit_id")
    audit_date = _required_string(config.get("audit_date"), "audit_date")
    try:
        date.fromisoformat(audit_date)
    except ValueError as exc:
        raise AuditError("audit_date must use YYYY-MM-DD") from exc

    perceptual = config.get("perceptual_hash")
    _require(isinstance(perceptual, dict), "perceptual_hash must be an object")
    _require(
        perceptual.get("algorithm") == PERCEPTUAL_ALGORITHM,
        f"perceptual_hash.algorithm must be {PERCEPTUAL_ALGORITHM}",
    )
    threshold = perceptual.get("max_hamming_distance")
    _require(isinstance(threshold, int) and 0 <= threshold <= 16, "invalid perceptual threshold")
    sample_size = config.get("manual_review_sample_size_per_label")
    _require(
        isinstance(sample_size, int) and 1 <= sample_size <= 100,
        "manual_review_sample_size_per_label must be between 1 and 100",
    )

    manifest_sources = {source["id"]: source for source in manifest["sources"]}
    source_items = config.get("sources")
    _require(isinstance(source_items, list) and source_items, "sources must be a non-empty list")
    specs: List[SourceAuditSpec] = []
    seen_ids = set()
    seen_envs = set()
    for index, item in enumerate(source_items):
        _require(isinstance(item, dict), f"sources[{index}] must be an object")
        source_id = _required_string(item.get("source_id"), f"sources[{index}].source_id")
        _require(source_id not in seen_ids, f"duplicate audit source: {source_id}")
        _require(source_id in manifest_sources, f"audit source is absent from manifest: {source_id}")
        _require(
            manifest_sources[source_id].get("status") == "APTO_PARA_AUDITORIA",
            f"source is not APTO_PARA_AUDITORIA: {source_id}",
        )
        version = _required_string(item.get("version"), f"{source_id}.version")
        root_env = _required_string(item.get("root_env"), f"{source_id}.root_env")
        _require(ROOT_ENV_RE.fullmatch(root_env) is not None, f"invalid root environment name: {root_env}")
        _require(root_env not in seen_envs, f"duplicate root environment name: {root_env}")

        splits = item.get("splits")
        _require(isinstance(splits, dict) and splits, f"{source_id}.splits must be an object")
        safe_splits: Dict[str, str] = {}
        for split_name, split_path in splits.items():
            clean_name = _required_string(split_name, f"{source_id}.split name")
            clean_path = _safe_relative(_required_string(split_path, f"{source_id}.{clean_name}"))
            safe_splits[clean_name] = clean_path
        _require(
            len(set(safe_splits.values())) == len(safe_splits),
            f"{source_id}.splits contains duplicate paths",
        )

        labels = item.get("allowed_labels")
        _require(isinstance(labels, list) and labels, f"{source_id}.allowed_labels must be non-empty")
        clean_labels = tuple(sorted({_required_string(value, f"{source_id}.allowed_labels") for value in labels}))
        _require(len(clean_labels) == len(labels), f"{source_id}.allowed_labels contains duplicates")

        extensions = item.get("extensions")
        _require(isinstance(extensions, list) and extensions, f"{source_id}.extensions must be non-empty")
        clean_extensions = tuple(sorted({_normalize_extension(value) for value in extensions}))
        _require(len(clean_extensions) == len(extensions), f"{source_id}.extensions contains duplicates")
        unknown_extensions = sorted(set(clean_extensions) - EXPECTED_FORMAT_BY_EXTENSION.keys())
        _require(not unknown_extensions, f"unsupported configured extension(s): {', '.join(unknown_extensions)}")

        review_status = item.get("manual_review_status")
        _require(review_status in {"PENDING", "COMPLETED"}, f"{source_id}.manual_review_status is invalid")
        identifiers = item.get("group_identifiers")
        _require(isinstance(identifiers, dict), f"{source_id}.group_identifiers must be an object")
        _require(
            all(name in identifiers for name in ("tree", "session", "farm"))
            and all(isinstance(value, bool) for value in identifiers.values()),
            f"{source_id}.group_identifiers must declare boolean tree/session/farm fields",
        )

        specs.append(
            SourceAuditSpec(
                source_id=source_id,
                version=version,
                root_env=root_env,
                splits=dict(sorted(safe_splits.items())),
                allowed_labels=clean_labels,
                extensions=clean_extensions,
                manual_review_status=review_status,
                group_identifiers=dict(sorted(identifiers.items())),
            )
        )
        seen_ids.add(source_id)
        seen_envs.add(root_env)

    return AuditConfig(
        audit_id=audit_id,
        audit_date=audit_date,
        perceptual_distance_threshold=threshold,
        manual_review_sample_size_per_label=sample_size,
        sources=tuple(sorted(specs, key=lambda item: item.source_id)),
    )


def roots_from_environment(config: AuditConfig, environ: Mapping[str, str]) -> Dict[str, Path]:
    roots = {}
    missing = []
    for spec in config.sources:
        raw_path = environ.get(spec.root_env, "").strip()
        if not raw_path:
            missing.append(spec.root_env)
        else:
            roots[spec.source_id] = Path(raw_path)
    if missing:
        raise AuditError(
            "missing authorized local dataset root(s): "
            + ", ".join(missing)
            + ". No data was downloaded and no report was written."
        )
    return roots


def audit_dataset_roots(
    config: AuditConfig,
    manifest: Dict[str, Any],
    roots: Mapping[str, Path],
    config_sha256: Optional[str] = None,
    manifest_sha256: Optional[str] = None,
) -> Dict[str, Any]:
    manifest_sources = {source["id"]: source for source in manifest["sources"]}
    resolved_roots: Dict[str, Path] = {}
    for spec in config.sources:
        root = roots.get(spec.source_id)
        _require(root is not None, f"missing root binding for {spec.source_id}")
        try:
            resolved = root.expanduser().resolve(strict=True)
        except OSError as exc:
            raise AuditError(f"local root for {spec.source_id} is unavailable: {exc}") from exc
        _require(resolved.is_dir(), f"local root for {spec.source_id} is not a directory")
        resolved_roots[spec.source_id] = resolved

    records: List[Dict[str, Any]] = []
    issues: List[Dict[str, Any]] = []
    snapshot_paths: Dict[str, List[Tuple[str, Path]]] = defaultdict(list)
    source_counts: Dict[str, Dict[str, int]] = {}

    for spec in config.sources:
        root = resolved_roots[spec.source_id]
        seen_paths = set()
        discovered = 0
        for split, relative_split in spec.splits.items():
            split_root = _resolve_inside(root, root / relative_split, f"split {split}")
            if not split_root.exists() or not split_root.is_dir():
                issues.append(_issue("missing_split", "error", spec.source_id, split=split))
                continue
            for candidate in sorted(split_root.rglob("*"), key=lambda value: value.as_posix()):
                if candidate.is_symlink():
                    discovered += 1
                    issues.append(
                        _issue(
                            "unsafe_path",
                            "error",
                            spec.source_id,
                            split=split,
                            path=_redacted_relative(root, candidate),
                        )
                    )
                    continue
                if candidate.is_dir():
                    continue
                discovered += 1
                relative = _relative_or_issue(root, candidate)
                if relative is None:
                    issues.append(
                        _issue(
                            "unsafe_path",
                            "error",
                            spec.source_id,
                            split=split,
                            path=_redacted_relative(root, candidate),
                        )
                    )
                    continue
                if relative in seen_paths:
                    raise AuditError(f"overlapping split paths include the same file: {relative}")
                seen_paths.add(relative)
                snapshot_paths[spec.source_id].append((relative, candidate))
                record, file_issues = _inspect_file(candidate, relative, split_root, split, spec)
                records.append(record)
                issues.extend(file_issues)
        source_counts[spec.source_id] = {"discovered_files": discovered}

    if not any(value["discovered_files"] for value in source_counts.values()):
        raise NoDataError("no local files were found in configured split directories; no report was written")

    records.sort(key=lambda item: (item["source_id"], item["relative_path"]))
    exact_groups, near_pairs = _find_duplicates(records, config.perceptual_distance_threshold)
    for group in exact_groups:
        if group["cross_split"] or group["cross_source"]:
            issues.append(
                {
                    "code": "exact_duplicate_leakage",
                    "severity": "error",
                    "members": group["members"],
                }
            )
    for pair in near_pairs:
        if pair["cross_split"] or pair["cross_source"]:
            issues.append(
                {
                    "code": "near_duplicate_leakage",
                    "severity": "error",
                    "members": pair["members"],
                    "distance": pair["distance"],
                }
            )

    integrity_by_source = {}
    for spec in config.sources:
        source_records = [record for record in records if record["source_id"] == spec.source_id]
        before = _snapshot_fingerprint(snapshot_paths[spec.source_id], use_record_hashes=source_records)
        after = _snapshot_fingerprint(snapshot_paths[spec.source_id])
        unchanged = before == after
        if not unchanged:
            issues.append(_issue("input_changed_during_audit", "error", spec.source_id))
        integrity_by_source[spec.source_id] = {
            "before_sha256": before,
            "after_sha256": after,
            "unchanged": unchanged,
        }

    issues.sort(key=_issue_sort_key)
    errors = sum(issue["severity"] == "error" for issue in issues)
    warnings = sum(issue["severity"] == "warning" for issue in issues)
    valid_records = [record for record in records if record["decode_status"] == "valid"]
    count_by_split = Counter(f"{record['source_id']}:{record['split']}" for record in records)
    count_by_label = Counter(f"{record['source_id']}:{record['label']}" for record in records)
    has_pending_review = any(spec.manual_review_status != "COMPLETED" for spec in config.sources)
    has_group_ids = all(all(spec.group_identifiers.values()) for spec in config.sources)

    source_report = []
    for spec in config.sources:
        source = manifest_sources[spec.source_id]
        source_report.append(
            {
                "source_id": spec.source_id,
                "version": spec.version,
                "license": {
                    "declared": source["license"]["declared"],
                    "spdx": source["license"].get("spdx"),
                    "evidence_urls": source["license"]["evidence_urls"],
                },
                "root_env": spec.root_env,
                "splits": spec.splits,
                "allowed_labels": list(spec.allowed_labels),
                "manual_review_status": spec.manual_review_status,
                "group_identifiers": spec.group_identifiers,
                "input_integrity": integrity_by_source[spec.source_id],
            }
        )

    limitations = []
    if not has_group_ids:
        limitations.append(
            "Tree, session or farm identifiers are missing; an original or file-level "
            "split does not demonstrate field generalization."
        )
    if has_pending_review:
        limitations.append("Manual per-class image review is pending.")
    limitations.append(
        "Perceptual matches are review candidates, not proof that two captures are the "
        "same; compression, crop and rotation can cause false positives or false negatives."
    )

    review_samples = _manual_review_samples(
        valid_records,
        config.manual_review_sample_size_per_label,
    )
    split_manifest_sha256 = _split_manifest_fingerprint(records)

    return {
        "schema_version": 1,
        "audit_id": config.audit_id,
        "audit_date": config.audit_date,
        "engine": {
            "name": ENGINE_NAME,
            "version": ENGINE_VERSION,
            "perceptual_hash": {
                "algorithm": PERCEPTUAL_ALGORITHM,
                "bits": 64,
                "max_hamming_distance": config.perceptual_distance_threshold,
            },
        },
        "provenance": {
            "config_sha256": config_sha256,
            "dataset_manifest_sha256": manifest_sha256,
        },
        "sources": source_report,
        "summary": {
            "file_count": len(records),
            "valid_image_count": len(valid_records),
            "invalid_file_count": len(records) - len(valid_records),
            "issue_error_count": errors,
            "issue_warning_count": warnings,
            "counts_by_source_split": dict(sorted(count_by_split.items())),
            "counts_by_source_label": dict(sorted(count_by_label.items())),
            "exact_duplicate_group_count": len(exact_groups),
            "near_duplicate_pair_count": len(near_pairs),
        },
        "files": records,
        "duplicates": {
            "exact_groups": exact_groups,
            "near_pairs": near_pairs,
        },
        "manual_review_samples": review_samples,
        "issues": issues,
        "limitations": limitations,
        "result": {
            "audit_status": "PASS" if errors == 0 else "FAIL",
            "split_leakage_detected": any(
                issue["code"] in {"exact_duplicate_leakage", "near_duplicate_leakage"}
                for issue in issues
            ),
            "split_freeze_ready": errors == 0 and not has_pending_review,
            "split_manifest_sha256": split_manifest_sha256,
            "clinical_quality_assessed": False,
        },
    }


def render_markdown(report: Dict[str, Any]) -> str:
    summary = report["summary"]
    result = report["result"]
    lines = [
        "# Resumen de auditoria de imagenes",
        "",
        f"- Auditoria: `{report['audit_id']}` ({report['audit_date']})",
        f"- Resultado tecnico: `{result['audit_status']}`",
        f"- Archivos inventariados: {summary['file_count']}",
        f"- Imagenes decodificadas: {summary['valid_image_count']}",
        f"- Archivos invalidos: {summary['invalid_file_count']}",
        f"- Grupos duplicados exactos: {summary['exact_duplicate_group_count']}",
        f"- Pares casi duplicados: {summary['near_duplicate_pair_count']}",
        f"- Fuga entre particiones: {'SI' if result['split_leakage_detected'] else 'NO'}",
        f"- Particiones listas para congelar: {'SI' if result['split_freeze_ready'] else 'NO'}",
        "",
        "## Fuentes",
        "",
    ]
    for source in report["sources"]:
        lines.append(
            f"- `{source['source_id']}` version `{source['version']}`; licencia "
            f"`{source['license']['declared']}`; revision manual `{source['manual_review_status']}`."
        )
    lines.extend(["", "## Recuentos por fuente y particion", ""])
    for name, count in summary["counts_by_source_split"].items():
        lines.append(f"- `{name}`: {count}")
    lines.extend(["", "## Incidencias", ""])
    if report["issues"]:
        for issue in report["issues"]:
            context = issue.get("path") or ", ".join(issue.get("members", []))
            lines.append(f"- `{issue['severity']}` `{issue['code']}`: {context or 'sin ruta'}")
    else:
        lines.append("- Ninguna incidencia tecnica detectada.")
    lines.extend(["", "## Limites", ""])
    lines.extend(f"- {item}" for item in report["limitations"])
    lines.append("")
    return "\n".join(lines)


def canonical_json(report: Dict[str, Any]) -> str:
    return json.dumps(report, ensure_ascii=True, indent=2, sort_keys=True) + "\n"


def write_reports(
    report: Dict[str, Any],
    json_path: Path,
    markdown_path: Path,
    replace: bool = False,
) -> None:
    json_content = canonical_json(report)
    markdown_content = render_markdown(report)
    _ensure_writable_report(json_path, json_content, replace)
    _ensure_writable_report(markdown_path, markdown_content, replace)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    _atomic_write(json_path, json_content)
    _atomic_write(markdown_path, markdown_content)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _inspect_file(
    path: Path,
    relative: str,
    split_root: Path,
    split: str,
    spec: SourceAuditSpec,
) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    size = path.stat().st_size
    sha256 = sha256_file(path)
    path_under_split = path.relative_to(split_root)
    label = path_under_split.parts[0] if len(path_under_split.parts) > 1 else "UNKNOWN"
    extension = path.suffix.lower()
    record: Dict[str, Any] = {
        "source_id": spec.source_id,
        "source_version": spec.version,
        "relative_path": relative,
        "split": split,
        "label": label,
        "size_bytes": size,
        "extension": extension,
        "sha256": sha256,
        "decode_status": "invalid",
        "format": None,
        "width": None,
        "height": None,
        "orientation": None,
        "orientation_verified": False,
        "decoder": None,
        "perceptual_hash": None,
    }
    issues = []
    if label not in spec.allowed_labels:
        issues.append(_issue("unknown_label", "error", spec.source_id, split, relative))
    if size == 0:
        issues.append(_issue("empty_file", "error", spec.source_id, split, relative))
        return record, issues
    if extension not in spec.extensions:
        issues.append(_issue("unexpected_format", "error", spec.source_id, split, relative))
        return record, issues
    try:
        decoded = decode_image(path)
    except (OSError, ImageDecodeError) as exc:
        issues.append(
            _issue(
                "corrupt_or_unsupported_image",
                "error",
                spec.source_id,
                split,
                relative,
                type(exc).__name__,
            )
        )
        return record, issues

    record.update(
        {
            "decode_status": "valid",
            "format": decoded.image_format,
            "width": decoded.width,
            "height": decoded.height,
            "orientation": decoded.orientation,
            "orientation_verified": decoded.orientation_verified,
            "decoder": decoded.decoder,
            "perceptual_hash": dhash64(decoded),
        }
    )
    expected_formats = EXPECTED_FORMAT_BY_EXTENSION.get(extension, set())
    if decoded.image_format not in expected_formats:
        issues.append(_issue("extension_format_mismatch", "error", spec.source_id, split, relative))
    if not decoded.orientation_verified:
        issues.append(_issue("orientation_unverified", "warning", spec.source_id, split, relative))
    return record, issues


def _find_duplicates(
    records: Sequence[Dict[str, Any]], threshold: int
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    valid = [record for record in records if record["decode_status"] == "valid"]
    by_sha: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for record in valid:
        by_sha[record["sha256"]].append(record)
    exact_groups = []
    for sha256, group in sorted(by_sha.items()):
        if len(group) < 2:
            continue
        members = [_member_id(item) for item in sorted(group, key=_record_key)]
        exact_groups.append(
            {
                "sha256": sha256,
                "members": members,
                "cross_split": len({item["split"] for item in group}) > 1,
                "cross_source": len({item["source_id"] for item in group}) > 1,
            }
        )

    near_pairs = []
    for left_index, left in enumerate(valid):
        for right in valid[left_index + 1 :]:
            if left["sha256"] == right["sha256"]:
                continue
            distance = hamming_distance(left["perceptual_hash"], right["perceptual_hash"])
            if distance <= threshold:
                near_pairs.append(
                    {
                        "members": sorted([_member_id(left), _member_id(right)]),
                        "distance": distance,
                        "cross_split": left["split"] != right["split"],
                        "cross_source": left["source_id"] != right["source_id"],
                    }
                )
    near_pairs.sort(key=lambda item: (item["distance"], item["members"]))
    return exact_groups, near_pairs


def _manual_review_samples(
    records: Sequence[Dict[str, Any]], sample_size: int
) -> Dict[str, Dict[str, List[str]]]:
    grouped: Dict[str, Dict[str, List[Dict[str, Any]]]] = defaultdict(lambda: defaultdict(list))
    for record in records:
        grouped[record["source_id"]][record["label"]].append(record)
    result = {}
    for source_id, labels in sorted(grouped.items()):
        result[source_id] = {}
        for label, items in sorted(labels.items()):
            ordered = sorted(items, key=lambda item: (item["sha256"], item["relative_path"]))
            result[source_id][label] = [_member_id(item) for item in ordered[:sample_size]]
    return result


def _split_manifest_fingerprint(records: Sequence[Dict[str, Any]]) -> str:
    digest = hashlib.sha256()
    for record in sorted(records, key=_record_key):
        digest.update(
            (
                f"{record['source_id']}\0{record['source_version']}\0"
                f"{record['relative_path']}\0{record['split']}\0{record['label']}\0"
                f"{record['sha256']}\n"
            ).encode("utf-8")
        )
    return digest.hexdigest()


def _snapshot_fingerprint(
    paths: Sequence[Tuple[str, Path]],
    use_record_hashes: Optional[Sequence[Dict[str, Any]]] = None,
) -> str:
    known_hashes = {}
    if use_record_hashes is not None:
        known_hashes = {record["relative_path"]: record["sha256"] for record in use_record_hashes}
    digest = hashlib.sha256()
    for relative, path in sorted(paths):
        if not path.exists() or path.is_symlink():
            digest.update(f"{relative}\0MISSING\n".encode("utf-8"))
            continue
        file_hash = known_hashes.get(relative) or sha256_file(path)
        digest.update(f"{relative}\0{path.stat().st_size}\0{file_hash}\n".encode("utf-8"))
    return digest.hexdigest()


def _resolve_inside(root: Path, candidate: Path, field: str) -> Path:
    try:
        resolved = candidate.resolve(strict=False)
        resolved.relative_to(root)
    except (OSError, ValueError) as exc:
        raise AuditError(f"{field} resolves outside its dataset root") from exc
    return resolved


def _relative_or_issue(root: Path, candidate: Path) -> Optional[str]:
    try:
        resolved = candidate.resolve(strict=True)
        resolved.relative_to(root)
        return candidate.relative_to(root).as_posix()
    except (OSError, ValueError):
        return None


def _redacted_relative(root: Path, candidate: Path) -> str:
    try:
        return candidate.relative_to(root).as_posix()
    except ValueError:
        return "UNSAFE_PATH_REDACTED"


def _safe_relative(value: str) -> str:
    path = Path(value)
    _require(not path.is_absolute(), f"path must be relative: {value}")
    _require(value not in {"", "."} and ".." not in path.parts, f"unsafe relative path: {value}")
    return path.as_posix()


def _normalize_extension(value: Any) -> str:
    extension = _required_string(value, "extension").lower()
    _require(extension.startswith(".") and "/" not in extension, f"invalid extension: {extension}")
    return extension


def _member_id(record: Dict[str, Any]) -> str:
    return f"{record['source_id']}:{record['relative_path']}"


def _record_key(record: Dict[str, Any]) -> Tuple[str, str]:
    return record["source_id"], record["relative_path"]


def _issue(
    code: str,
    severity: str,
    source_id: str,
    split: Optional[str] = None,
    path: Optional[str] = None,
    detail: Optional[str] = None,
) -> Dict[str, Any]:
    issue: Dict[str, Any] = {"code": code, "severity": severity, "source_id": source_id}
    if split is not None:
        issue["split"] = split
    if path is not None:
        issue["path"] = path
    if detail is not None:
        issue["detail"] = detail
    return issue


def _issue_sort_key(issue: Dict[str, Any]) -> Tuple[str, str, str, str]:
    return (
        issue.get("code", ""),
        issue.get("source_id", ""),
        issue.get("split", ""),
        issue.get("path", "") or ",".join(issue.get("members", [])),
    )


def _required_string(value: Any, field: str) -> str:
    _require(isinstance(value, str) and value.strip(), f"{field} must be a non-empty string")
    return value.strip()


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AuditError(message)


def _ensure_writable_report(path: Path, content: str, replace: bool) -> None:
    if path.exists() and path.read_text(encoding="utf-8") != content and not replace:
        raise AuditError(
            f"refusing to overwrite historical report {path}; rerun with explicit replacement after review"
        )


def _atomic_write(path: Path, content: str) -> None:
    temporary = path.with_name(path.name + f".tmp-{os.getpid()}")
    temporary.write_text(content, encoding="utf-8")
    temporary.replace(path)
