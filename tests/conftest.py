from __future__ import annotations

import shutil
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def model_repository(tmp_path: Path) -> Path:
    """Return a writable copy of a small, complete dataset repository."""
    destination = tmp_path / "model-repository"
    shutil.copytree(FIXTURES / "model_repository", destination)
    consumer_test = destination / "tests/test_people.py.fixture"
    consumer_test.rename(consumer_test.with_suffix(""))
    return destination


@pytest.fixture
def legacy_jekyll_repository(tmp_path: Path) -> Path:
    """Return a writable copy of a repository using the old Jekyll layout."""
    destination = tmp_path / "legacy-repository"
    shutil.copytree(FIXTURES / "legacy_jekyll_repository", destination)
    return destination


@pytest.fixture
def notebook_file() -> Path:
    return FIXTURES / "notebooks" / "analysis.ipynb"
