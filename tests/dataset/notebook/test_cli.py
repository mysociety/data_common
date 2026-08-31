from __future__ import annotations

from pathlib import Path

import pytest

from data_common.notebookcli.discovery import load_document_collection


def test_notebook_cli_discovers_repository_from_nested_directory(
    model_repository: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Load render configuration from the repository rather than the installed package.
    """
    (model_repository / "render.yaml").write_text(
        """
analysis:
  title: Portable analysis
  slug: portable-analysis
  notebooks:
    - analysis
""".lstrip()
    )
    nested_directory = model_repository / "data" / "packages" / "people"
    monkeypatch.chdir(nested_directory)

    collection = load_document_collection()

    assert collection.repo_root == model_repository
    assert collection.get("analysis").title == "Portable analysis"
