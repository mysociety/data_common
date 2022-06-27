import json
from pathlib import Path
from typing import Any
import shutil
from ruamel.yaml import YAML
import pandas as pd

from .settings import get_settings
from .version_management import map_versions_to_latest_major_minor


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
    for e in output_dir.glob("*/*.md"):
        e.unlink()

    for dataset in items:
        datapackage_path = output_dir / f"{dataset['name']}"
        if datapackage_path.exists() is False:
            datapackage_path.mkdir()
        markdown_file = datapackage_path / f"{dataset['version']}.md"
        markdown_with_frontmatter(dataset, markdown_file)


def fill_in_versions():
    """
    Copy the latest version of each dataset to the latest major/minor version
    """
    data_dir = get_settings()["publish_dir"] / "data"

    datapackages = data_dir.glob("*/*/datapackage.json")
    datapackages = list(set([x.parent.parent for x in datapackages]))
    for package_folder in datapackages:
        full_versions = [str(x).split("/")[-1] for x in package_folder.glob(("*.*.*/"))]
        assert len(full_versions) > 0, f"No versions found for {package_folder}"
        version_map = map_versions_to_latest_major_minor(full_versions)
        for reduced, full in version_map.items():
            full_path = package_folder / full
            reduced_path = package_folder / reduced
            if reduced_path.exists():
                shutil.rmtree(reduced_path)
            shutil.copytree(full_path, reduced_path)
            print(f"Copied {full} to {reduced}")


def make_version_info_page(items: list[dict[str, Any]], output_dir: Path):
    """
    Make a page for each dataset that contains a list of all the versions
    avaliable and major, minor, and latest versions link to another dataset
    """

    if output_dir.exists() is False:
        output_dir.mkdir()
    # remove existing files
    for e in output_dir.glob("*/*.md"):
        e.unlink()

    df = pd.DataFrame(items)[["name", "title", "version", "full_version"]]

    for name, d in df.groupby("name"):
        safe_name = name.replace("-", "_")
        data_dict = {
            "name": name,
            "title": d["title"].iloc[0],
            "versions": {},
            "permalink": f"/datasets/{safe_name}/versions",
        }
        d = d.sort_values("full_version", ascending=False)
        for gv, rd in d.groupby("full_version"):
            items = rd["version"].apply(str).to_list()
            items.sort()
            data_dict["versions"][str(gv)] = items

        markdown_file = output_dir / f"{safe_name}.md"
        markdown_with_frontmatter(data_dict, markdown_file)


def collect_jekyll_data():
    """
    Collect information from data packages published to Jekyll
    into the data directory where it can access them
    """
    data_dir = get_settings()["publish_dir"] / "data"

    def grab_version(package_folder: Path):
        data = json.loads(package_folder.read_text())
        data["full_version"] = data["version"]
        data["version"] = package_folder.parent.name
        data["permalink"] = (
            "/datasets/" + data["name"] + "/" + data["version"].replace(".", "_")
        )
        return data

    all_packages = [grab_version(d) for d in data_dir.glob("*/*/datapackage.json")]

    resources = []

    for a in all_packages:
        resources.extend(collect_jekyll_data_for_package(a))

    render_sources_to_dir(
        all_packages, output_dir=get_settings()["publish_dir"] / "_datasets"
    )

    make_version_info_page(
        all_packages, output_dir=get_settings()["publish_dir"] / "_versionlists"
    )

    render_sources_to_dir(
        resources, output_dir=get_settings()["publish_dir"] / "_downloads"
    )


def collect_jekyll_data_for_package(package: dict[str, Any]):
    """
    Collect information from data packages published to Jekyll
    into the data directory where it can access them
    """

    all_resources: list[dict[str, str]] = []

    package_level_download_options = {}
    custom_options = package.get("custom", {})
    if "download_options" in custom_options:
        download_options = custom_options["download_options"]
        gate_type = download_options.get("gate", "default")
        survey_ref = download_options.get("survey", "default")
        header_text = download_options.get("header_text", "default")
        if gate_type != "default":
            package_level_download_options["download_gate_type"] = gate_type
        if survey_ref != "default":
            package_level_download_options["download_survey"] = survey_ref
        if header_text != "default":
            package_level_download_options["download_form_header"] = header_text
    for r in package["resources"]:
        r["download_id"] = "_".join([package["name"], r["name"]]).replace("_", "-")
        download_data = {
            "name": r["download_id"],
            "permalink": "/downloads/"
            + r["download_id"]
            + "/"
            + package["version"].replace(".", "_"),
            "package": package["name"],
            "title": r["name"],
            "filename": r["path"],
            "version": package["version"],
            "full_version": package["version"],
            "file": f"/data/{package['name']}/{package['version']}/{r['path']}",
        }
        download_data.update(package_level_download_options)
        all_resources.append(download_data)

    xlsx_data = {
        "name": (package["name"] + "_xlsx").replace("_", "-"),
        "permalink": f"/downloads/{package['name']}_xlsx/{package['version'].replace('.', '_')}",
        "package": package["name"],
        "title": package["name"] + "_xlsx",
        "filename": f"{package['name']}.xlsx",
        "version": package["version"],
        "full_version": package["version"],
        "file": f"/data/{package['name']}/{package['version']}/{package['name']}.xlsx",
    }
    json_data = {
        "name": (package["name"] + "_json").replace("_", "-"),
        "permalink": f"/downloads/{package['name']}_json/{package['version'].replace('.', '_')}",
        "package": package["name"],
        "title": package["name"] + "_json",
        "filename": f"{package['name']}.json",
        "version": package["version"],
        "full_version": package["version"],
        "file": f"/data/{package['name']}/{package['version']}/{package['name']}.json",
    }
    xlsx_data.update(package_level_download_options)
    all_resources.append(xlsx_data)
    all_resources.append(json_data)
    return all_resources


def render_jekyll():
    fill_in_versions()
    collect_jekyll_data()
