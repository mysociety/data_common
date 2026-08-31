from __future__ import annotations

import json
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import toml
from ruamel.yaml import YAML

from .migration_models import (
    LegacyJekyllConfiguration,
    MigrationDownloadSettings,
    MigrationReport,
    MigrationSiteSettings,
)


def load_legacy_jekyll(path: Path) -> LegacyJekyllConfiguration:
    """
    Load the subset of legacy Jekyll configuration used by migration.
    """
    if not path.is_file():
        return LegacyJekyllConfiguration()
    value = YAML(typ="safe").load(path.read_text())
    return LegacyJekyllConfiguration.model_validate(
        value if isinstance(value, Mapping) else {}
    )


def index_intro(path: Path, fallback: str) -> str:
    """
    Extract introductory Markdown from a legacy Jekyll index page.
    """
    if not path.is_file():
        return fallback
    content = path.read_text()
    if content.startswith("---"):
        _, separator, remainder = content[3:].partition("---")
        if separator:
            content = remainder
    content = content.strip()
    heading = re.compile(r"^#\s+.*?(?:\n+|$)")
    content = heading.sub("", content, count=1).strip()
    return content or fallback


def download_settings(
    config: LegacyJekyllConfiguration,
) -> MigrationDownloadSettings:
    """
    Translate legacy download-page defaults to Flask-site settings.
    """
    gate = "soft"
    survey = ""
    form_header = "Can you help us by telling us more about yourself?"
    for item in config.defaults:
        if item.scope.type != "downloads":
            continue
        values = item.values
        if values.download_gate_type is not None:
            gate = values.download_gate_type
        if values.download_survey is not None:
            survey = values.download_survey
        if values.download_form_header is not None:
            form_header = values.download_form_header
    return MigrationDownloadSettings(
        gate=gate,
        survey=survey,
        form_header=form_header,
    )


def site_settings(
    root: Path,
    project: Mapping[str, Any],
    jekyll: LegacyJekyllConfiguration,
) -> MigrationSiteSettings:
    """
    Derive typed Flask-site settings from project and Jekyll configuration.
    """
    raw_project = project.get("project", {})
    project_data = raw_project if isinstance(raw_project, Mapping) else {}
    project_name = str(project_data.get("name", root.name))
    project_description = str(project_data.get("description", ""))
    title = jekyll.title or project_name
    description = jekyll.description or project_description
    base_url = jekyll.baseurl.rstrip("/")
    host = jekyll.url.rstrip("/")
    canonical = host + base_url if host else ""
    return MigrationSiteSettings(
        title=title,
        description=description,
        intro=index_intro(root / "docs" / "index.md", description),
        base_url=base_url,
        canonical_url=canonical,
        source_url=f"https://github.com/mysociety/{root.name}",
        downloads=download_settings(jekyll),
    )


def replace_toml_value(
    content: str,
    table_name: str,
    key: str,
    value: str,
) -> str:
    """
    Replace or append one string value in a TOML table.
    """
    lines = content.splitlines()
    header = f"[{table_name}]"
    try:
        start = lines.index(header)
    except ValueError as error:
        raise ValueError(f"Missing {header} in pyproject.toml") from error
    end = next(
        (
            index
            for index in range(start + 1, len(lines))
            if lines[index].startswith("[")
        ),
        len(lines),
    )
    replacement = f"{key} = {json.dumps(value)}"
    for index in range(start + 1, end):
        if re.match(rf"\s*{re.escape(key)}\s*=", lines[index]):
            lines[index] = replacement
            return "\n".join(lines) + "\n"
    lines.insert(end, replacement)
    return "\n".join(lines) + "\n"


def site_toml(settings: MigrationSiteSettings) -> str:
    """
    Serialize generated site settings as TOML tables.
    """
    scalar_keys = (
        "title",
        "description",
        "intro",
        "base_url",
        "canonical_url",
        "source_url",
        "output_dir",
        "accent_colour",
    )
    values = settings.model_dump()
    lines = ["[tool.dataset.site]"]
    lines.extend(
        f"{key} = {json.dumps(values[key])}"
        for key in scalar_keys
        if values.get(key) is not None
    )
    lines.extend(["", "[tool.dataset.site.downloads]"])
    lines.extend(
        f"{key} = {json.dumps(value)}"
        for key, value in settings.downloads.model_dump().items()
    )
    lines.extend(["", "[tool.dataset.site.analysis]"])
    lines.extend(
        f"{key} = {json.dumps(value)}"
        for key, value in settings.analysis.model_dump().items()
    )
    return "\n".join(lines) + "\n"


def update_pyproject(
    path: Path,
    *,
    settings: MigrationSiteSettings,
    apply: bool,
    report: MigrationReport,
) -> None:
    """
    Update dataset publication and site settings in pyproject.toml.
    """
    parsed = toml.load(path)
    content = path.read_text()
    updated = replace_toml_value(
        content,
        "tool.dataset",
        "publish_dir",
        "data/packages/_published",
    )
    existing = parsed.get("tool", {}).get("dataset", {}).get("site")
    if not existing:
        updated = updated.rstrip() + "\n\n" + site_toml(settings)
        report.actions.append("add [tool.dataset.site] configuration")
    else:
        updated = replace_toml_value(
            updated,
            "tool.dataset.site",
            "output_dir",
            "_site",
        )
        if existing.get("output_dir") != "_site":
            report.actions.append("set tool.dataset.site.output_dir to _site")
    if updated != content:
        report.actions.append(
            "set tool.dataset.publish_dir to data/packages/_published"
        )
        if apply:
            path.write_text(updated)


def convert_notebook_configs(
    root: Path,
    *,
    apply: bool,
    report: MigrationReport,
) -> None:
    """
    Rename legacy Jekyll notebook upload targets to site targets.
    """
    paths = [root / "render.yaml"]
    paths.extend(sorted((root / "notebooks" / "_render_config").glob("*.yaml")))
    yaml = YAML()
    for path in paths:
        if not path.is_file():
            continue
        data = yaml.load(path.read_text())
        changed = False
        for document in data.values() if isinstance(data, dict) else []:
            if not isinstance(document, dict):
                continue
            uploads = document.get("upload")
            if isinstance(uploads, dict) and "jekyll" in uploads:
                uploads.setdefault("site", uploads.pop("jekyll"))
                changed = True
        if changed:
            report.actions.append(
                f"rename upload.jekyll to upload.site in {path.relative_to(root)}"
            )
            if apply:
                with path.open("w") as stream:
                    yaml.dump(data, stream)
