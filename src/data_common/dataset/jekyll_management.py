import json
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML

from .settings import get_settings

markdown_template = """
---
{content}
---
"""


def markdown_with_frontmatter(data: dict[str, Any], dest: Path, content: str = ""):

    yaml = YAML()
    yaml.default_flow_style = False

    with open(dest, "w") as f:
        f.write("---\n")
        yaml.dump(data, f)
        f.write("---\n")
        if content:
            f.write(content)


def render_sources_to_dir(items: list[dict[str, Any]], output_dir: Path):

    if output_dir.exists() is False:
        output_dir.mkdir()
    # remove existing files
    for e in output_dir.glob("*.md"):
        e.unlink()

    for dataset in items:
        markdown_file = output_dir / f"{dataset['name']}.md"
        markdown_with_frontmatter(dataset, markdown_file)


def collect_jekyll_data():
    """
    Collect information from data packages published to Jekyll
    into the data directory where it can access them
    """
    data_dir = get_settings()["publish_dir"] / "data"

    all_packages = [
        json.loads(d.read_text()) for d in data_dir.glob("*/datapackage.json")
    ]

    all_resources = []
    for package in all_packages:
        package["composite"] = {"xlsx": (package["name"] + "_xlsx").replace("_", "-")}
        for r in package["resources"]:
            r["download_id"] = "_".join([package["name"], r["name"]]).replace("_", "-")
            all_resources.append(
                {
                    "name": r["download_id"],
                    "package": package["name"],
                    "title": r["name"],
                    "filename": r["path"],
                    "file": f"/data/{package['name']}/{r['path']}",
                }
            )
        all_resources.append(
            {
                "name": (package["name"] + "_xlsx").replace("_", "-"),
                "package": package["name"],
                "title": package["name"] + "_xlsx",
                "filename": f"{package['name']}.xlsx",
                "file": f"/data/{package['name']}/{package['name']}.xlsx",
            }
        )

    render_sources_to_dir(
        all_packages, output_dir=get_settings()["publish_dir"] / "_datasets"
    )
    render_sources_to_dir(
        all_resources, output_dir=get_settings()["publish_dir"] / "_downloads"
    )