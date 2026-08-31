from __future__ import annotations

from pathlib import Path

import toml

from data_common.dataset.site.migration import migrate_repository


def test_migration_is_safe_idempotent_and_can_ignore_publication(
    legacy_jekyll_repository: Path,
) -> None:
    root = legacy_jekyll_repository
    docs = root / "docs"

    dry_run = migrate_repository(root, ignore_published=True)
    assert dry_run.changed
    assert docs.exists()
    assert not (root / "data/packages/_published").exists()

    applied = migrate_repository(root, apply=True, ignore_published=True)
    assert applied.applied
    assert not docs.exists()
    assert (
        root / "data/packages/_published/data/example/latest/datapackage.json"
    ).is_file()
    assert "data/packages/_published/" in (root / ".gitignore").read_text()
    assert "docs/theme" not in (root / ".gitmodules").read_text()

    workflow = (root / ".github/workflows/build.yml").read_text()
    assert "Build with Jekyll" not in workflow
    assert "dataset site build" in workflow
    assert "path: _site" in workflow

    dataset = toml.load(root / "pyproject.toml")["tool"]["dataset"]
    assert dataset["publish_dir"] == "data/packages/_published"
    assert dataset["site"]["title"] == "Legacy data"
    assert dataset["site"]["output_dir"] == "_site"
    assert dataset["site"]["downloads"]["survey"] == "survey-id"

    assert not migrate_repository(root, ignore_published=True).changed


def test_migration_refuses_unrecognised_docs_content(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "legacy"\n\n[tool.dataset]\npublish_dir = "docs"\n'
    )
    (tmp_path / "docs").mkdir()
    unexpected = tmp_path / "docs/hand-written.html"
    unexpected.write_text("keep me")

    try:
        migrate_repository(tmp_path, apply=True)
    except ValueError as error:
        assert "unexpected entries" in str(error)
    else:
        raise AssertionError("Migration should refuse unknown docs content")

    assert unexpected.read_text() == "keep me"
    assert (
        toml.load(tmp_path / "pyproject.toml")["tool"]["dataset"]["publish_dir"]
        == "docs"
    )
    assert not (tmp_path / ".gitignore").exists()
