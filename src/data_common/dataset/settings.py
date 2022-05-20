from functools import lru_cache
from pathlib import Path
from typing import TypedDict

import toml


class SettingsDict(TypedDict):
    publish_dir: Path
    dataset_dir: Path
    publish_url: str
    credit_text: str
    credit_url: str


@lru_cache
def get_settings(toml_file: str = "pyproject.toml") -> SettingsDict:
    """
    Get basic data settings
    """

    top_level: list[str] = []
    attempt = 0
    while Path(*top_level, toml_file).exists() is False and attempt < 10:
        top_level.append("..")
        attempt += 1
    if Path(*top_level, toml_file).exists() is False:
        raise ValueError("Can't find top level pyproject.toml")

    settings_file = Path(*top_level, toml_file)

    data = toml.load(settings_file)["tool"]["dataset"]

    data["publish_dir"] = Path(*top_level, data["publish_dir"])
    data["dataset_dir"] = Path(*top_level, data["dataset_dir"])

    return data
