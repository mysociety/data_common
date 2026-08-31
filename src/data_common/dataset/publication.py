from __future__ import annotations

import shutil
from pathlib import Path

from .settings import get_settings
from .version_management import map_versions_to_latest_major_minor


def publish_version_aliases(data_dir: Path | None = None) -> dict[str, dict[str, str]]:
    root = data_dir or get_settings().publish_dir / "data"
    package_folders = sorted(
        {path.parent.parent for path in root.glob("*/*/datapackage.json")}
    )
    published: dict[str, dict[str, str]] = {}

    for package_folder in package_folders:
        full_versions = [
            path.name
            for path in package_folder.iterdir()
            if path.is_dir() and len(path.name.split(".")) == 3 and "-" not in path.name
        ]
        if not full_versions:
            raise ValueError(f"No full semantic versions found for {package_folder}")

        version_map = map_versions_to_latest_major_minor(full_versions)
        published[package_folder.name] = version_map
        for alias, full_version in version_map.items():
            source = package_folder / full_version
            destination = package_folder / alias
            if destination.exists():
                shutil.rmtree(destination)
            shutil.copytree(source, destination)
            print(f"Copied {full_version} to {alias}")

    return published
