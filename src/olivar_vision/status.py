"""Read the human-maintained project status from README.md."""

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List


TRACKED_FIELDS = (
    "Estado documentado",
    "Fase activa",
    "Extension LiDAR-carbono",
    "Ultimo hito completado",
    "Comprobaciones realizadas",
    "Siguiente accion",
)


@dataclass(frozen=True)
class ProjectStatus:
    """Small machine-readable view of the README live status."""

    fields: Dict[str, str]

    def get(self, name: str) -> str:
        return self.fields.get(name, "NO DOCUMENTADO")

    def as_lines(self) -> List[str]:
        return [f"{field}: {self.get(field)}" for field in TRACKED_FIELDS]


def _normalize_heading(line: str) -> str:
    return line.strip().lstrip("#").strip().lower()


def extract_section(lines: Iterable[str], heading: str) -> List[str]:
    """Return the lines under a Markdown heading until the next heading."""

    wanted = heading.strip().lower()
    captured: List[str] = []
    in_section = False

    for line in lines:
        if line.lstrip().startswith("#"):
            current = _normalize_heading(line)
            if in_section and current != wanted:
                break
            in_section = current == wanted
            continue

        if in_section:
            captured.append(line.rstrip("\n"))

    return captured


def parse_status(readme_text: str) -> ProjectStatus:
    section = extract_section(readme_text.splitlines(), "Estado vivo")
    fields: Dict[str, str] = {}

    for raw_line in section:
        line = raw_line.strip()
        if not line.startswith("- "):
            continue
        item = line[2:]
        if ":" not in item:
            continue
        key, value = item.split(":", 1)
        normalized = key.strip().strip("*")
        fields[normalized] = value.strip()

    next_action = extract_section(readme_text.splitlines(), "Siguiente accion")
    if next_action:
        compact = " ".join(line.strip() for line in next_action if line.strip())
        if compact:
            fields["Siguiente accion"] = compact

    return ProjectStatus(fields=fields)


def load_status(path: Path) -> ProjectStatus:
    return parse_status(path.read_text(encoding="utf-8"))
