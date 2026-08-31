from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import toml
from pydantic import BaseModel, ConfigDict


class DatasetSettings(BaseModel):
    """
    Hold resolved repository-level dataset configuration.
    """

    model_config = ConfigDict(frozen=True)

    repo_root: Path
    publish_dir: Path
    dataset_dir: Path
    publish_url: str = ""
    credit_text: str = ""
    credit_url: str = ""


def find_repo_root(start: Path | None = None) -> Path:
    """
    Find the nearest parent directory containing pyproject.toml.
    """
    current = (start or Path.cwd()).resolve()
    for candidate in (current, *current.parents):
        if (candidate / "pyproject.toml").is_file():
            return candidate
    raise ValueError("Could not find a pyproject.toml from the current directory")


def resolve_settings_path(
    toml_file: str | Path = "pyproject.toml",
    *,
    repo_root: Path | None = None,
) -> Path:
    """
    Resolve the settings file independently of the process working directory.
    """
    path = Path(toml_file)
    if path.is_absolute():
        return path.resolve()
    root = repo_root.resolve() if repo_root else find_repo_root()
    return (root / path).resolve()


@lru_cache
def load_settings(settings_file: Path) -> DatasetSettings:
    """
    Load and validate settings for one absolute configuration path.
    """
    config = toml.load(settings_file)
    data = config.get("tool", {}).get("dataset", {})
    root = settings_file.parent
    publish_dir = Path(data.get("publish_dir", "data/packages/_published"))
    dataset_dir = Path(data.get("dataset_dir", "data/packages"))
    return DatasetSettings(
        repo_root=root,
        publish_dir=publish_dir if publish_dir.is_absolute() else root / publish_dir,
        dataset_dir=dataset_dir if dataset_dir.is_absolute() else root / dataset_dir,
        publish_url=str(data.get("publish_url", "")),
        credit_text=str(data.get("credit_text", "")),
        credit_url=str(data.get("credit_url", "")),
    )


def get_settings(
    toml_file: str | Path = "pyproject.toml",
    *,
    repo_root: Path | None = None,
) -> DatasetSettings:
    """
    Return validated settings cached by their absolute configuration path.
    """
    return load_settings(resolve_settings_path(toml_file, repo_root=repo_root))
