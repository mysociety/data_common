from __future__ import annotations

from pathlib import Path

import toml

from .migration_config import (
    convert_notebook_configs,
    load_legacy_jekyll,
    site_settings,
    update_pyproject,
)
from .migration_files import (
    move_data_and_remove_docs,
    preflight_migration,
    remove_ruby_layers,
    remove_theme_checkout,
    remove_theme_submodule,
    update_actions_lock,
    update_gitignore,
    update_server_script,
    update_workflow,
)
from .migration_models import MigrationReport


def migrate_repository(
    repo_root: Path | None = None,
    *,
    apply: bool = False,
    force: bool = False,
    ignore_published: bool = False,
) -> MigrationReport:
    """
    Plan or apply migration from the legacy Jekyll publication layout.
    """
    root = (repo_root or Path.cwd()).resolve()
    pyproject_path = root / "pyproject.toml"
    if not pyproject_path.is_file():
        raise ValueError(f"No pyproject.toml found in {root}")

    preflight_migration(root, force=force)
    report = MigrationReport(repo_root=root, applied=apply)
    project = toml.load(pyproject_path)
    jekyll = load_legacy_jekyll(root / "docs" / "_config.yml")
    settings = site_settings(root, project, jekyll)

    update_pyproject(
        pyproject_path,
        settings=settings,
        apply=apply,
        report=report,
    )
    update_gitignore(
        root / ".gitignore",
        ignore_published=ignore_published,
        apply=apply,
        report=report,
    )
    remove_theme_submodule(root / ".gitmodules", apply=apply, report=report)
    convert_notebook_configs(root, apply=apply, report=report)
    remove_ruby_layers(root / "Dockerfile", apply=apply, report=report)
    update_server_script(root / "script" / "server", apply=apply, report=report)
    for workflow_name in ("build.yml", "test.yml"):
        update_workflow(
            root / ".github" / "workflows" / workflow_name,
            apply=apply,
            report=report,
        )
    update_actions_lock(
        root / ".github" / "workflows" / "actions.lock",
        apply=apply,
        report=report,
    )
    for script_path in (
        root / ".devcontainer" / "postCreateCommand",
        root / "script" / "update-from-template",
    ):
        remove_theme_checkout(script_path, apply=apply, report=report)
    move_data_and_remove_docs(
        root,
        apply=apply,
        force=force,
        report=report,
    )
    return report


__all__ = ["MigrationReport", "migrate_repository"]
