from __future__ import annotations

import re
import shutil
from pathlib import Path

from miniclaw.agent.skills import BUILTIN_SKILLS_DIR

_SKILL_NAME_SANITIZER = re.compile(r"[^a-z0-9-]+")
_FRONTMATTER = re.compile(r"^---\n(.*?)\n---\n?", re.DOTALL)


def list_skills(workspace: Path) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    seen: set[str] = set()

    for source, root in (
        ("workspace", workspace / "skills"),
        ("builtin", BUILTIN_SKILLS_DIR),
    ):
        if not root.exists():
            continue
        for skill_dir in root.iterdir():
            if not skill_dir.is_dir():
                continue
            skill_file = skill_dir / "SKILL.md"
            if not skill_file.exists():
                continue
            metadata = read_skill_metadata(skill_file.read_text(encoding="utf-8"))
            name = metadata.get("name") or skill_dir.name
            if name in seen:
                continue
            seen.add(name)
            items.append(
                {
                    "name": name,
                    "path": str(skill_file),
                    "source": source,
                    "description": metadata.get("description", ""),
                }
            )
    return items


def get_skill(workspace: Path, name: str) -> dict[str, str] | None:
    for item in list_skills(workspace):
        if item["name"] != name:
            continue
        content = Path(item["path"]).read_text(encoding="utf-8")
        return {
            **item,
            "content": strip_frontmatter(content),
        }
    return None


def import_skill(workspace: Path, filename: str, content: bytes) -> dict[str, str]:
    raw = content.decode("utf-8")
    metadata = read_skill_metadata(raw)
    raw_name = metadata.get("name") or Path(filename).stem
    normalized_name = normalize_skill_name(raw_name)
    skill_dir = workspace / "skills" / normalized_name
    skill_file = skill_dir / "SKILL.md"
    if skill_dir.exists():
        raise FileExistsError("skill already exists")

    description = metadata.get("description") or infer_description(strip_frontmatter(raw)) or "Imported skill"
    normalized = f"---\nname: {normalized_name}\ndescription: {description}\n---\n\n{strip_frontmatter(raw).lstrip()}"
    skill_dir.mkdir(parents=True, exist_ok=False)
    skill_file.write_text(normalized.rstrip() + "\n", encoding="utf-8")
    return {
        "name": normalized_name,
        "path": str(skill_file),
        "source": "workspace",
        "description": description,
    }


def delete_skill(workspace: Path, name: str) -> bool:
    for item in list_skills(workspace):
        if item["name"] == name and item["source"] == "workspace":
            shutil.rmtree(Path(item["path"]).parent)
            return True
    return False


def normalize_skill_name(name: str) -> str:
    lowered = name.strip().lower().replace("_", "-").replace(" ", "-")
    lowered = _SKILL_NAME_SANITIZER.sub("-", lowered).strip("-")
    lowered = re.sub(r"-{2,}", "-", lowered)
    if not lowered:
        raise ValueError("skill name is required")
    if len(lowered) > 64:
        raise ValueError("skill name exceeds 64 characters")
    return lowered


def read_skill_metadata(content: str) -> dict[str, str]:
    match = _FRONTMATTER.match(content)
    if not match:
        return {}
    result: dict[str, str] = {}
    for line in match.group(1).splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        result[key.strip()] = value.strip().strip("'\"")
    return result


def strip_frontmatter(content: str) -> str:
    return _FRONTMATTER.sub("", content, count=1)


def infer_description(content: str) -> str:
    for line in content.splitlines():
        cleaned = line.strip().lstrip("#-*0123456789. ").strip()
        if cleaned:
            return cleaned[:256]
    return ""
