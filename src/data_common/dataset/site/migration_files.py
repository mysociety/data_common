from __future__ import annotations

import re
import shutil
from pathlib import Path

from .migration_models import MigrationReport

LEGACY_DOC_ENTRIES = {
    ".gitinclude",
    "Gemfile",
    "Gemfile.lock",
    "_analysis",
    "_config.yml",
    "_datasets",
    "_downloads",
    "_site",
    "_versionlists",
    "data",
    "data.json",
    "index.md",
    "sass",
    "theme",
}


def update_gitignore(
    path: Path,
    *,
    ignore_published: bool,
    apply: bool,
    report: MigrationReport,
) -> None:
    """
    Apply the selected publication and generated-site ignore policy.
    """
    content = path.read_text() if path.exists() else ""
    publication_entry = "data/packages/_published"
    lines = [
        line
        for line in content.splitlines()
        if line.rstrip("/")
        not in {"docs/_site", "_site", "published", publication_entry}
    ]
    lines.append("_site/")
    if ignore_published:
        lines.append(f"{publication_entry}/")
    updated = "\n".join(lines) + "\n"
    if updated != content:
        policy = "ignore" if ignore_published else "track"
        report.actions.append(f"ignore _site and {policy} data/packages/_published")
        if apply:
            path.write_text(updated)


def remove_theme_submodule(
    path: Path,
    *,
    apply: bool,
    report: MigrationReport,
) -> None:
    """
    Remove the legacy theme submodule declaration.
    """
    if not path.is_file():
        return
    content = path.read_text()
    pattern = re.compile(r'(?ms)^\[submodule "docs/theme"\]\n.*?(?=^\[submodule |\Z)')
    updated = pattern.sub("", content).rstrip() + "\n"
    if updated != content:
        report.actions.append("remove the docs/theme submodule declaration")
        if apply:
            path.write_text(updated)


def remove_ruby_layers(
    path: Path,
    *,
    apply: bool,
    report: MigrationReport,
) -> None:
    """
    Remove Ruby copy layers from a legacy Dockerfile.
    """
    if not path.is_file():
        return
    original = path.read_text()
    lines = original.splitlines()
    updated: list[str] = []
    skipping = False
    for line in lines:
        if line.startswith("COPY --from=ruby:"):
            skipping = line.rstrip().endswith("\\")
            continue
        if skipping:
            skipping = line.rstrip().endswith("\\")
            continue
        updated.append(line)
    content = "\n".join(updated) + "\n"
    if content != original:
        report.actions.append("remove Ruby layers from Dockerfile")
        if apply:
            path.write_text(content)


def update_server_script(
    path: Path,
    *,
    apply: bool,
    report: MigrationReport,
) -> None:
    """
    Replace a legacy Jekyll development server command.
    """
    if not path.is_file() or "jekyll" not in path.read_text().lower():
        return
    report.actions.append("replace script/server with dataset site serve")
    if apply:
        path.write_text("#!/bin/bash\nset -e\nuv run dataset site serve\n")


def update_workflow(
    path: Path,
    *,
    apply: bool,
    report: MigrationReport,
) -> None:
    """
    Replace Jekyll build steps and legacy output paths in one workflow.
    """
    if not path.is_file():
        return
    original = path.read_text()
    lines = original.splitlines()
    updated: list[str] = []
    index = 0
    while index < len(lines):
        line = lines[index]
        if line.strip() == "- name: Build with Jekyll":
            indent = len(line) - len(line.lstrip())
            index += 1
            while index < len(lines):
                candidate = lines[index]
                candidate_indent = len(candidate) - len(candidate.lstrip())
                if candidate.lstrip().startswith("- ") and candidate_indent == indent:
                    break
                if candidate.strip() and candidate_indent < indent:
                    break
                index += 1
            continue
        updated.append(line.replace("path: docs/_site", "path: _site"))
        index += 1

    command = "dataset site check" if path.name == "test.yml" else "dataset site build"
    if command not in original:
        for command_index, line in enumerate(updated):
            if "dataset version " in line:
                indentation = line[: len(line) - len(line.lstrip())]
                updated.insert(command_index + 1, indentation + command)
                break

    content = "\n".join(updated) + "\n"
    if content != original:
        report.actions.append(f"convert {path.relative_to(path.parents[2])} to Flask")
        if apply:
            path.write_text(content)


def update_actions_lock(
    path: Path,
    *,
    apply: bool,
    report: MigrationReport,
) -> None:
    """
    Remove the obsolete Jekyll build action from the actions lock.
    """
    if not path.is_file():
        return
    original = path.read_text()
    content = re.sub(
        r"(?m)^\s+- 'actions/jekyll-build-pages@[^']+'\n",
        "",
        original,
    )
    content = re.sub(
        r"(?ms)^    'actions/jekyll-build-pages@[^']+':\n.*?(?=^    '[^']+':|\Z)",
        "",
        content,
    )
    if content != original:
        report.actions.append("remove the Jekyll action from the actions lock")
        if apply:
            path.write_text(content)


def remove_theme_checkout(
    path: Path,
    *,
    apply: bool,
    report: MigrationReport,
) -> None:
    """
    Remove shell commands that updated the legacy theme submodule.
    """
    if not path.is_file():
        return
    original = path.read_text()
    content = re.sub(
        r"(?ms)^cd docs/theme\n.*?(?:^cd \.\./\.\.\n?|\Z)",
        "",
        original,
    )
    if content != original:
        report.actions.append(
            f"remove the theme checkout from {path.relative_to(path.parents[1])}"
        )
        if apply:
            path.write_text(content)


def unexpected_docs_entries(root: Path) -> list[str]:
    """
    Return legacy docs entries that are unsafe to remove automatically.
    """
    docs = root / "docs"
    if not docs.exists():
        return []
    return sorted(
        entry.name for entry in docs.iterdir() if entry.name not in LEGACY_DOC_ENTRIES
    )


def preflight_migration(root: Path, *, force: bool) -> None:
    """
    Validate destructive migration steps before changing any repository files.
    """
    unexpected = unexpected_docs_entries(root)
    if unexpected and not force:
        raise ValueError(
            "Refusing to remove docs; unexpected entries found: "
            + ", ".join(unexpected)
            + ". Move them first or review and rerun with --force."
        )

    docs = root / "docs"
    source_exists = any(
        path.exists() for path in (docs / "data", root / "published" / "data")
    )
    destination = root / "data" / "packages" / "_published" / "data"
    if source_exists and destination.exists():
        raise ValueError(
            "Cannot migrate publication data: destination already exists at "
            f"{destination}"
        )


def move_data_and_remove_docs(
    root: Path,
    *,
    apply: bool,
    force: bool,
    report: MigrationReport,
) -> None:
    """
    Move published data and remove the reviewed legacy docs directory.
    """
    docs = root / "docs"
    destination = root / "data" / "packages" / "_published"
    destination_data = destination / "data"
    candidates = (docs / "data", root / "published" / "data")
    source_data = next((path for path in candidates if path.exists()), None)

    unexpected = unexpected_docs_entries(root)
    if unexpected and not force:
        names = ", ".join(unexpected)
        raise ValueError(
            f"Refusing to remove docs; unexpected entries found: {names}. "
            "Move them first or review and rerun with --force."
        )
    if unexpected:
        report.warnings.append(
            "removing unrecognised docs entries because --force was used: "
            + ", ".join(unexpected)
        )

    if source_data is not None and destination_data.exists():
        raise ValueError(
            f"Cannot move {source_data}: destination already exists at "
            f"{destination_data}"
        )

    if source_data is not None:
        report.actions.append(
            f"move {source_data.relative_to(root)} to data/packages/_published/data"
        )
        if apply:
            destination.mkdir(parents=True, exist_ok=True)
            shutil.move(str(source_data), str(destination_data))
            old_publication_dir = root / "published"
            if (
                source_data.parent == old_publication_dir
                and old_publication_dir.exists()
                and not any(old_publication_dir.iterdir())
            ):
                old_publication_dir.rmdir()

    if docs.exists():
        report.actions.append("remove the legacy docs directory")
        if apply:
            shutil.rmtree(docs)
