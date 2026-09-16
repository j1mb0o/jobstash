"""Filesystem store for named search configs (one JSON file per search)."""

import json
import re
from pathlib import Path

from pydantic import ValidationError

from src.schemas.search_config import SearchConfig

_SAFE_NAME_PATTERN = re.compile(r"[^a-z0-9\-_ ]+", re.IGNORECASE)
EXAMPLE_SUFFIX = ".example.json"


class SearchConfigError(ValueError):
    """Raised for unreadable, corrupt, or unsafe search config files."""


def slugify_name(name: str) -> str:
    """Map a display name to a safe filename stem."""
    slug = _SAFE_NAME_PATTERN.sub("", name.strip().lower()).strip()
    slug = re.sub(r"[\s_]+", "-", slug)
    slug = re.sub(r"-{2,}", "-", slug).strip("-")
    if not slug:
        raise SearchConfigError(f"Config name {name!r} has no usable characters.")
    if len(slug) > 80:
        slug = slug[:80].rstrip("-")
    return slug


def ensure_config_dir(config_dir: Path) -> Path:
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


def config_path_for(config_dir: Path, name: str) -> Path:
    return config_dir / f"{slugify_name(name)}.json"


def list_config_names(config_dir: Path) -> list[str]:
    """Return sorted config names, skipping ``*.example.json`` templates."""
    if not config_dir.is_dir():
        return []
    names: list[str] = []
    for path in sorted(config_dir.glob("*.json")):
        if path.name.endswith(EXAMPLE_SUFFIX):
            continue
        try:
            config = load_config_file(path)
        except SearchConfigError:
            continue
        names.append(config.name)
    return sorted(names)


def list_config_files(config_dir: Path) -> list[Path]:
    """Return sorted runnable config files, skipping example templates."""
    if not config_dir.is_dir():
        return []
    return sorted(
        path
        for path in config_dir.glob("*.json")
        if not path.name.endswith(EXAMPLE_SUFFIX)
    )


def load_config_file(path: Path) -> SearchConfig:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SearchConfigError(f"Config file not found: {path}") from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise SearchConfigError(f"Config file {path} is not valid JSON: {exc}") from exc
    try:
        return SearchConfig.model_validate(payload)
    except ValidationError as exc:
        raise SearchConfigError(f"Config file {path} is invalid: {exc}") from exc


def find_config_file(config_dir: Path, name: str) -> Path:
    """Resolve a user-supplied name or path to its JSON file.

    A value containing a path separator or ending in ``.json`` is treated as
    a file path (resolved against the current directory, so tab-completion
    like ``configs/my-search.json`` works). Otherwise matches, in order:
    ``<slug>.json`` directly, then each runnable file by filename stem (raw
    or slugified), then by the config's internal ``name`` field (raw or
    slugified).
    """
    candidate = name.strip()
    if candidate.endswith(".json") or "/" in candidate or "\\" in candidate:
        path = Path(candidate).expanduser()
        if not path.is_absolute():
            path = Path.cwd() / path
        if not path.is_file():
            raise SearchConfigError(f"Config file not found: {candidate}")
        if path.suffix.lower() != ".json":
            raise SearchConfigError(f"Config file must be JSON: {candidate}")
        return path
    slug = slugify_name(name)
    direct = config_dir / f"{slug}.json"
    if direct.is_file():
        return direct
    for path in list_config_files(config_dir):
        try:
            stem_matches = path.stem == name or slugify_name(path.stem) == slug
        except SearchConfigError:
            stem_matches = False
        if stem_matches:
            return path
        try:
            config = load_config_file(path)
        except SearchConfigError:
            continue
        if config.name == name or slugify_name(config.name) == slug:
            return path
    available = [path.stem for path in list_config_files(config_dir)]
    hint = f" Available: {', '.join(available)}." if available else ""
    raise SearchConfigError(
        f"Unknown search config: {name!r} (looked for {direct.name}).{hint}"
    )


def load_config_by_name(config_dir: Path, name: str) -> SearchConfig:
    return load_config_file(find_config_file(config_dir, name))


def save_config(config_dir: Path, config: SearchConfig) -> Path:
    """Persist a config atomically; overwrites the same slug."""
    ensure_config_dir(config_dir)
    target = config_path_for(config_dir, config.name)
    payload = config.model_dump(mode="json")
    text = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    tmp_path = target.with_suffix(".json.tmp")
    tmp_path.write_text(text, encoding="utf-8")
    tmp_path.replace(target)
    return target
