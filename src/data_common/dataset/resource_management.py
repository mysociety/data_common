from __future__ import annotations

import importlib
import json
import re
import shutil
import sqlite3
import subprocess
import warnings
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from shutil import copyfile
from typing import Any, Literal, NamedTuple, TypeVar
from urllib.parse import urlencode

import geopandas as gpd
import numpy as np
import pandas as pd
import rich
from frictionless import validate
from rich.table import Table
from ruamel.yaml import YAML

from data_common.db import duck_query

from .package_models import CompositeOptions, DataPackageExtras
from .publication import publish_version_aliases
from .resources import DataResource
from .rich_assist import PanelPrint, df_to_table
from .settings import get_settings
from .testing import run_dataset_tests
from .version_management import (
    bump_version,
    is_valid_semver,
    parse_semver,
    semver_is_higher,
)


class ValueDifference(NamedTuple):
    """
    Hold previous and current values for one changed key.
    """

    previous: Any
    current: Any


def diff_dicts(
    a: Mapping[str, Any],
    b: Mapping[str, Any],
) -> dict[str, ValueDifference]:
    """
    Return changed values shared by two nested mappings.
    """
    differences: dict[str, ValueDifference] = {}
    for key in set(a).union(b):
        previous = a.get(key)
        current = b.get(key)
        if previous != current:
            differences[key] = ValueDifference(previous, current)
    return differences


version_rules = Literal["MAJOR", "MINOR", "PATCH", "INITIAL"]


alert_colors = Literal["red", "green", "orange", "blue"]


class ValidationErrorItem(NamedTuple):
    """
    Pair a validation message with its terminal display colour.
    """

    message: str
    colour: alert_colors


ValidationErrors = list[ValidationErrorItem]


def make_color(item: str, color: alert_colors) -> str:
    return f"[{color}]{item}[/{color}]"


def color_print(item: str, color: alert_colors, new_line: bool = True) -> None:
    rich.print(make_color(item, color), end="\n" if new_line else " ")


@dataclass
class DataPackage:
    path: Path

    @property
    def extras(self) -> DataPackageExtras:
        """
        Return typed application metadata from the datapackage custom field.
        """
        return DataPackageExtras.from_datapackage(self.get_datapackage())

    @property
    def slug(self) -> str:
        """
        Generally the folder name, unless we're opening an old version
        """
        if self.path.parent.stem == "versions":
            return self.path.parent.parent.stem
        else:
            return self.path.stem

    @property
    def datapackage_path(self) -> Path:
        return self.path / "datapackage.yaml"

    def test_package(self, quiet: bool = False) -> bool:
        """
        Run the tests configured for this package in an isolated process.

        A package can list test filenames without extensions in custom.tests.
        If it does not, test_<package slug>.py is used when present.
        Explicitly configured missing tests fail the package.
        """
        test_dir = self.path.parent.parent.parent / "tests"
        configured_names = tuple(self.extras.tests)
        if configured_names:
            paths = tuple(test_dir / f"{name}.py" for name in configured_names)
            missing = tuple(path for path in paths if not path.is_file())
            if missing:
                rich.print(
                    "[red]Configured dataset tests do not exist: "
                    + ", ".join(str(path) for path in missing)
                    + "[/red]"
                )
                return False
        else:
            default_path = test_dir / f"test_{self.slug}.py"
            if not default_path.is_file():
                if not quiet:
                    rich.print("[yellow]No dataset-specific tests configured[/yellow]")
                return True
            paths = (default_path,)

        if not quiet:
            rich.print("[blue]Running tests[/blue]")
        result = run_dataset_tests(
            paths,
            repo_root=test_dir.parent,
            quiet=quiet,
        )
        return result.passed

    def build_from_function(self) -> None:
        """
        Function to build data from a function specified in a module.
        """
        build_module = self.extras.build.strip()
        if not build_module:
            rich.print(
                "[red]No build command or python path specified in custom.build in the yaml[/red]"
            )
            return
        if ":" in build_module and " " not in build_module:
            module, function = build_module.split(":")
            module = importlib.import_module(module)
            function = getattr(module, function)

            # run build function!
            rich.print(f"[blue]Running build function for {self.slug}[/blue]")
            function()
        else:
            # run shell command and get exit code
            rich.print(f"[blue]Running build command for {self.slug}[/blue]")
            exit_code = subprocess.call(build_module, shell=True)
            if exit_code != 0:
                raise ValueError(
                    f"Build command for {self.slug} failed with exit code {exit_code}"
                )

    def get_current_version(self) -> str:
        """
        Get the current version of the datapackage.yaml file.
        """
        desc = self.get_datapackage()
        version = str(desc["version"])
        if len(version.split(".")) == 2:
            version += ".0"
        return version

    def bump_version_on_rule(
        self,
        bump_rule: str,
        update_message: str,
        dry_run: bool = False,
        auto_ban: list[str] | None = None,
        publish: bool = False,
    ) -> None:
        """
        Bumps the version number of the datapackage according to the
        specified bump rule.

        Parameters
        ----------
        bump_rule : str
            The bump rule to use. Must be one of "MAJOR", "MINOR", "PATCH", "INITIAL", "STATIC",
            or "AUTO".

        Raises
        ------
        ValueError
            If the given bump rule is not valid.
        """
        if bump_rule not in ["MAJOR", "MINOR", "PATCH", "INITIAL", "AUTO", "STATIC"]:
            raise ValueError(f"{bump_rule} is not a valid bump_rule")
        current_version = self.get_current_version()
        force_static = bump_rule == "STATIC"
        auto_ban = auto_ban or []
        if bump_rule in ["AUTO", "STATIC"]:
            bump_results = self.derive_bump_rule_from_change()
            if bump_results:
                bump_rule, auto_update_message = bump_results
                if bump_rule in auto_ban:
                    raise ValueError(
                        f"The change caused by {update_message} is a {bump_rule} change, which is banned by the auto-ban rule."
                    )
                if update_message == "":
                    update_message = auto_update_message
            else:
                rich.print("[red]No changes detected, not bumping[/red]")
                return
        if bump_rule == "INITIAL":
            new_version = current_version
        elif force_static:
            rich.print(
                "[blue]Changes detected, but static rule means overriding current version[/blue]"
            )
            new_version = current_version
        else:
            new_version = bump_version(current_version, bump_rule.lower())

        self.bump_version_to(new_version, update_message, dry_run, publish=publish)
        if force_static and publish:
            rich.print("[blue]Republishing anyway, because static setting used[/blue]")
            self.rebuild_all_resources()
            self.build_package()
            self.build_missing_previous_versions()
            publish_version_aliases()

    def previous_versions(self) -> list[str]:
        """
        return names of valid versions stored in the versions folder
        """

        versions_path = self.path / "versions"

        if versions_path.exists() is False:
            versions_path.mkdir()

        return [x.name for x in versions_path.iterdir() if is_valid_semver(x.name)]

    def derive_bump_rule_from_change(self) -> tuple[version_rules, str] | None:
        """
        compares the current live version and the last stored version with the current version
        semver and returns the appropriate bump rule, and a reason for the bump.
        """

        MAJOR = "MAJOR"
        MINOR = "MINOR"
        PATCH = "PATCH"
        INITIAL = "INITIAL"

        version = self.get_current_version()

        parsed_version = parse_semver(version)
        # if  version is below 1, all major changes are minor
        if parsed_version and int(parsed_version["major"]) < 1:
            MAJOR = MINOR

        current_stored_path = self.path / "versions" / version
        if current_stored_path.exists() is False:
            if version == "0.1.0":
                return INITIAL, "Don't need to increment, first version"
            else:
                raise ValueError(
                    f"There is no {version} in the versions directory. Can't work out the change, specify new version name manually"
                )
        previous_datapackage = self.__class__(current_stored_path)
        current_data = self.get_current_datapackage_json()
        previous_data = previous_datapackage.get_current_datapackage_json()
        del current_data["custom"]
        del previous_data["custom"]

        # Following https://specs.frictionlessdata.io/patterns/#data-package-version
        # With the exception of adding new fields (at the end of the CSV), which is a new feature, and so a minor change.

        # check for any major differences

        # Change the data package, resource or field name or identifier

        if (p_name := previous_data.get("name")) != (
            c_name := current_data.get("name")
        ):
            return MAJOR, f"Datapackage name changed from {p_name} to {c_name}"
        if (p_identifier := previous_data.get("identifier")) != (
            c_identifier := current_data.get("identifier")
        ):
            return (
                MAJOR,
                f"Datapackage identifier changed from {p_identifier} to {c_identifier}",
            )

        # Add, remove or re-order fields
        # Also check if an old resource has been removed
        # With the exception of adding new fields (at the end of the CSV), which is a new feature, and so a minor change.
        for previous_resource in previous_data["resources"]:
            current_resource = [
                x
                for x in current_data["resources"]
                if x["name"] == previous_resource["name"]
            ]
            # check still exists
            if len(current_resource) == 0:
                return (
                    MAJOR,
                    f"Existing resource {previous_resource['title']} renamed or deleted",
                )

            current_resource = current_resource[0]

            # custom check here - is there a difference in the _sheet_order property?
            if previous_resource.get("_sheet_order") != current_resource.get(
                "_sheet_order"
            ):
                return (
                    MAJOR,
                    f"Sheet order changed for resource {previous_resource['title']}",
                )

            previous_field_names = [
                x["name"] for x in previous_resource["schema"]["fields"]
            ]
            current_field_names = [
                x["name"] for x in current_resource["schema"]["fields"]
            ]
            if set(previous_field_names) != set(current_field_names):
                # there is a difference to explore
                if len(previous_field_names) > len(current_field_names):
                    removed = ",".join(
                        set(previous_field_names) - set(current_field_names)
                    )
                    # removed fields
                    return MAJOR, f"Existing resource field(s) removed: {removed}"
                if len(previous_field_names) < len(current_field_names):
                    # added fields
                    # This is ok if fields are at the end
                    # check if new stuff is only at the end
                    new_fields = [
                        x for x in current_field_names if x not in previous_field_names
                    ]
                    new_fields = ",".join(new_fields)
                    if (
                        current_field_names[: len(previous_field_names)]
                        == previous_field_names
                    ):
                        return (
                            MINOR,
                            f"New field(s) added to end of resource: {new_fields}",
                        )
                    else:
                        return MAJOR, f"New field(s) added to resource: {new_fields}"

            # is a field type changed?
            old_field_name_and_type = [
                (x["name"], x["type"]) for x in previous_resource["schema"]["fields"]
            ]
            new_field_name_and_type = [
                (x["name"], x["type"]) for x in current_resource["schema"]["fields"]
            ]
            if set(old_field_name_and_type) != set(new_field_name_and_type):
                # given we've weeded out field name differences, this is a change to type
                changed_types = [
                    x
                    for x in new_field_name_and_type
                    if x not in old_field_name_and_type
                ]
                changed_types = ",".join([x[0] for x in changed_types])
                return (
                    MAJOR,
                    f"Existing resource field(s) type changed: {changed_types}",
                )

        # Licence change - should be Major level change
        if (p_license := previous_data.get("licenses")) != (
            c_license := current_data.get("licenses")
        ):
            return MAJOR, f"License changed from {p_license} to {c_license}"

        # Change a field constraint to be more restrictive
        # Not implimented

        # Check for minor differences

        # Has a new resources been added to a data package

        if len(previous_data["resources"]) < len(current_data["resources"]):
            # new resource added
            new_resources = [
                x
                for x in current_data["resources"]
                if x not in previous_data["resources"]
            ]
            new_resources = ",".join([x["name"] for x in new_resources])
            return MINOR, f"New resource(s) added: {new_resources}"

        # Add/remove new data to an existing data resource
        # get a list of all resources where the row count has changed
        old_row_counts = {
            x["name"]: x["custom"]["row_count"] for x in previous_data["resources"]
        }
        new_row_counts = {
            x["name"]: x["custom"]["row_count"] for x in current_data["resources"]
        }
        different_counts = [
            x for x in old_row_counts if old_row_counts[x] != new_row_counts[x]
        ]
        if len(different_counts) > 0:
            different_counts = ",".join(different_counts)
            return MINOR, f"Change in data for resource(s): {different_counts}"

        # Change a field constraint to be less restrictive
        # Not implimented

        # Update a reference to another data resource
        # Not implimented

        # Change data to reflect changes in referenced data
        # Not implimented

        # check for any patch level differences

        # Correct errors in existing data - no new rows or data, but a hash change
        old_hash_values = {x["name"]: x["hash"] for x in previous_data["resources"]}
        new_hash_values = {x["name"]: x["hash"] for x in current_data["resources"]}
        different_hash_values = [
            x for x in old_hash_values if old_hash_values[x] != new_hash_values[x]
        ]
        if len(different_hash_values) > 0:
            different_hash_values = ",".join(different_hash_values)
            return (
                PATCH,
                f"Minor change in data for resource(s): {different_hash_values}",
            )

        # Change descriptive metadata properties
        package_level_descriptive_variables = [
            "title",
            "description",
            "keywords",
            "sources",
            "contributors",
        ]
        for variable in package_level_descriptive_variables:
            if (p_variable := previous_data.get(variable)) != (
                c_variable := current_data.get(variable)
            ):
                return (
                    PATCH,
                    f"{variable} changed from '{p_variable}' to '{c_variable}'",
                )

        # check resource level descriptive variables
        resource_level_description_variables = ["title", "description", "keywords"]
        field_schema_level_description_variables = ["description", "example"]
        for previous_resource in previous_data["resources"]:
            current_resource = next(
                item
                for item in current_data["resources"]
                if item["name"] == previous_resource["name"]
            )
            for variable in resource_level_description_variables:
                if (p_variable := previous_resource.get(variable)) != (
                    c_variable := current_resource.get(variable)
                ):
                    return (
                        PATCH,
                        f"{current_resource['name']}: {variable} changed from {p_variable} to {c_variable}",
                    )

            previous_schema_fields = previous_resource["schema"]["fields"]
            current_schema_fields = current_resource["schema"]["fields"]
            for variable in field_schema_level_description_variables:
                for previous_field in previous_schema_fields:
                    current_field = next(
                        item
                        for item in current_schema_fields
                        if item["name"] == previous_field["name"]
                    )
                    if (p_variable := previous_field.get(variable)) != (
                        c_variable := current_field.get(variable)
                    ):
                        return (
                            PATCH,
                            f"{current_resource['name']}: {variable} changed from {p_variable} to {c_variable}",
                        )

        if current_data != previous_data:
            dict_diff = diff_dicts(previous_data, current_data)
            rich.print(dict_diff)

            # This catches differences in the hash value for instance
            raise ValueError(
                "There is a difference between the two files, not captured by the bump rule detection"
            )

    def bump_version_to(
        self,
        new_semver: str,
        update_message: str,
        dry_run: bool = False,
        publish: bool = False,
        prerelease: str = "",
    ) -> None:
        version = self.get_current_version()
        current_version_is_prerelease = "-" in version
        if current_version_is_prerelease:
            version = version.split("-")[0]
        desc = self.get_datapackage()
        # check if prerelease is valid format, only ASCII alphanumerics and hyphens
        if prerelease and not re.match(r"^[a-zA-Z0-9-]+$", prerelease):
            raise ValueError("Prerelease must be ASCII alphanumerics and hyphens")
        if prerelease:
            new_semver = f"{new_semver}-{prerelease}"
        if is_valid_semver(new_semver) is False:
            raise ValueError(f"{new_semver} is not valid semver")
        if (
            semver_is_higher(version, new_semver)
            or new_semver == "0.1.0"
            or (current_version_is_prerelease and (version == new_semver))
        ):
            # check if package is valid
            validation_errors = self.validate(quiet=False)
            if validation_errors:
                raise ValueError("Package is not valid, cannot update version.")

            # increment the version in the yaml and update change log
            extras = DataPackageExtras.from_datapackage(desc).with_change(
                new_semver,
                update_message,
            )
            if dry_run:
                rich.print("[yellow]Dry run, not updating.[/yellow]")
                rich.print(
                    f"[blue]Would update to version {new_semver} because of {update_message}[/blue]"
                )
            else:
                self.update_yaml(
                    {
                        "version": new_semver,
                        "custom": extras.as_datapackage_value(),
                    }
                )
                self.store_version()
                rich.print(f"{self.slug} version bumped to [green]{new_semver}[/green]")
                if publish:
                    self.rebuild_all_resources()
                    self.build_package()
                    self.build_missing_previous_versions()
                    publish_version_aliases()
        else:
            print(f"{new_semver} is not higher than {version} or is 0.1.0.")

    def store_version(self) -> None:
        """
        store all files in the top level directory of the package in a folder for this version.
        """
        top_level = self.path
        version = self.get_datapackage()["version"]
        version_dir = top_level / "versions" / version
        version_dir.mkdir(parents=True, exist_ok=True)
        for file in top_level.iterdir():
            if file.is_dir() is False:
                shutil.copy(file, version_dir / file.name)

    def update_yaml(self, new_values: dict[str, Any]) -> None:
        """
        Rebuild the yaml file with the new values
        """
        desc = self.get_datapackage()
        desc.update(new_values)
        yaml = YAML()
        yaml.default_flow_style = False
        with open(self.datapackage_path, "w") as f:
            yaml.dump(desc, f)

    def build_path(self, version: str = "") -> Path:
        if version == "":
            version = self.get_current_version()
        build_path = get_settings().publish_dir / "data" / self.slug / version
        if build_path.exists() is False:
            build_path.mkdir(parents=True, exist_ok=True)
        return build_path

    def __post_init__(self) -> None:
        if self.datapackage_path.exists() is False:
            raise ValueError(f"No datapackage.yaml found in {self.path}")

    def resources(self) -> dict[str, DataResource]:
        # a resource can be a csv or a parquet file
        resources = [DataResource(path=x) for x in self.path.glob("*.csv")]
        resources += [DataResource(path=x) for x in self.path.glob("*.parquet")]

        # check there aren't any csvs and paraquets with the same name
        if len({resource.path.stem for resource in resources}) != len(resources):
            raise ValueError(
                f"Found multiple resources with the same name in {self.path}"
            )

        resources.sort(key=lambda x: x.slug)
        new_order = {r.slug: r.get_order(n) for n, r in enumerate(resources)}
        resources.sort(key=lambda x: new_order[x.slug])
        return {x.slug: x for x in resources}

    @property
    def resource_count(self) -> int:
        return len(self.resources())

    @property
    def url(self) -> str:
        url = (
            get_settings().publish_url
            + "datasets/"
            + self.slug.replace("-", "_")
            + "/"
            + self.get_datapackage()["version"].replace(".", "_")
        )
        if "datasets/datasets" in url:
            url = url.replace("/datasets/datasets/", "/datasets/")
        return url

    def rebuild_resource(self, slug: str) -> None:
        resource = self.resources()[slug]
        resource.rebuild_yaml()

    def rebuild_all_resources(self) -> None:
        is_geodata = self.is_geodata()
        for resource in self.resources().values():
            resource.rebuild_yaml(is_geodata=is_geodata)

    def is_geodata(self) -> bool:
        return self.extras.is_geodata

    def get_datapackage(self) -> dict[str, Any]:
        yaml = YAML(typ="safe")
        with open(self.datapackage_path, "r"):
            return yaml.load(self.datapackage_path)

    def validate(self, quiet: bool = False) -> ValidationErrors:
        desc = self.get_datapackage()
        validation_errors: ValidationErrors = []
        if not desc.get("description", ""):
            validation_errors.append(
                ValidationErrorItem("Missing package description", "red")
            )
        if not desc.get("title", ""):
            validation_errors.append(
                ValidationErrorItem("Missing package title", "red")
            )
        if not desc.get("licenses", ""):
            validation_errors.append(
                ValidationErrorItem("Missing package licence", "red")
            )
        if self.test_package(quiet) is False:
            validation_errors.append(ValidationErrorItem("Tests failed", "red"))
        for r in self.resources().values():
            if r.get_status()[1] == "red":
                validation_errors.append(
                    ValidationErrorItem(f"Invalid resource {r.slug}", "red")
                )
        return validation_errors

    def past_versions(self) -> list[str]:
        """
        get a list of previous versions as avaliable in the versions folder
        """
        versions = []
        for version in self.path.glob("versions/*"):
            if version.is_dir():
                versions.append(version.name)
        return versions

    def build_missing_previous_versions(self) -> None:
        """
        Where source versions exist but their publication output is missing,
        build them.
        """

        for v in self.past_versions():
            build_path = self.build_path(v)
            if (build_path / "datapackage.json").exists() is False:
                color_print(f"Building missing {self.slug} version {v}", "red")
                previous = self.__class__(self.path / "versions" / v)
                previous.build_package()

    def build_package(self) -> None:
        """
        Build package files and move them to the publication data directory.
        """

        color_print(
            f"Building package: {self.slug} {self.get_current_version()}", "red"
        )
        color_print("Building datapackage.json", "blue", new_line=False)
        self.build_json()
        color_print("✔️", "green")
        color_print("Copying resources", "blue", new_line=False)
        self.copy_resources()
        color_print("✔️", "green")
        color_print("Checking package validity", "blue", new_line=False)
        self.check_build_integrity()
        color_print("✔️", "green")
        color_print("Building composite files", "blue", new_line=False)
        self.build_composites()
        color_print("✔️", "green")

    def check_build_integrity(self) -> None:
        """
        run the validator against the data pacakge
        """

        with warnings.catch_warnings():
            warnings.filterwarnings("ignore")
            valid_results = validate(
                self.build_path() / "datapackage.json", type="package"
            ).to_dict()
        if valid_results["stats"]["errors"] > 0:
            raise ValueError(valid_results)

    def copy_resources(self) -> None:
        """
        Copy the CSV/parquet over and create the opposite item.
        Use DUCKDB to make the conversion robust for larger files.
        """

        extras = self.extras
        formats = extras.formats

        csv_copy_query = """
        copy (select * from {{ source }}) to {{ dest }} (format PARQUET);
        """

        # __index_level_0__ is an internal parquet column that duckdb has access to
        # but we don't want to export
        exclude = ""
        if extras.is_geodata:
            exclude = "EXCLUDE (geometry)"

        parquet_copy_query = """
        copy (select * {{ exclude }} from {{ source }}) to {{ dest }} (HEADER, DELIMITER ',');
        """

        for r in self.resources().values():
            # need to have seperate handling for csv and paraquet
            if r.path.suffix == ".csv":
                if formats.csv:
                    copyfile(r.path, self.build_path() / r.path.name)
                if formats.parquet:
                    parquet_file = self.build_path() / (r.path.stem + ".parquet")
                    duck_query(csv_copy_query, source=r.path, dest=parquet_file).run()
                if formats.geojson or formats.gpkg:
                    raise ValueError(
                        "Writing to geojson/geopackage from csv source not supported. Use parquet internally."
                    )
            elif r.path.suffix == ".parquet":
                if formats.parquet:
                    copyfile(r.path, self.build_path() / r.path.name)
                if formats.csv:
                    csv_file = self.build_path() / (r.path.stem + ".csv")
                    duck_query(
                        parquet_copy_query,
                        exclude=exclude,
                        source=r.path,
                        dest=csv_file,
                    ).run()
                if formats.geojson:
                    geojson_path = self.build_path() / (r.path.stem + ".geojson")
                    gdf = gpd.read_parquet(r.path)
                    gdf.to_file(geojson_path, driver="GeoJSON")
                if formats.gpkg:
                    geopackage_path = self.build_path() / (r.path.stem + ".gpkg")
                    gdf = gpd.read_parquet(r.path)
                    gdf.to_file(geopackage_path, driver="GPKG")

    def get_datapackage_order(self) -> int:
        """
        Get any priority order between the datasets
        """
        return self.extras.dataset_order

    def get_current_datapackage_json(self) -> dict[str, Any]:
        """
        Get a dictionary representation of the current datapackage
        """
        datapackage = self.get_datapackage()
        datapackage["resources"] = [x.get_resource() for x in self.resources().values()]
        for resource in datapackage["resources"]:
            if "custom" not in resource:
                resource["custom"] = {}
            if "datasette" not in resource["custom"]:
                resource["custom"]["datasette"] = {}
            if "about" not in resource["custom"]["datasette"]:
                resource["custom"]["datasette"]["about"] = "Info & Downloads"
                resource["custom"]["datasette"]["about_url"] = (
                    f"{self.url}#{resource['name']}"
                )
        extras = DataPackageExtras.from_datapackage(datapackage).for_publication(
            self.url
        )
        datapackage["custom"] = extras.as_datapackage_value()
        return datapackage

    def build_json(self) -> None:
        """
        Create full json datapackage file for all resources
        """
        datapackage = self.get_current_datapackage_json()
        with open(self.build_path() / "datapackage.json", "w") as f:
            json.dump(datapackage, f, indent=4)

    def survey_url(self) -> str:
        """
        link to the info gathering custom survey relevant for this survey
        Either constructs from the pyproject default, or
        """
        settings = get_settings()
        default_survey_url = settings.credit_url
        specific_alchemer = self.extras.download_options.survey
        if specific_alchemer and specific_alchemer != "default":
            survey_url = "https://survey.alchemer.com/s3/" + specific_alchemer
        else:
            survey_url = default_survey_url
        survey_url += "?" + urlencode(
            {"dataset_slug": self.slug, "download_link": self.url}
        )
        return survey_url

    def build_coversheet(
        self, writer: pd.ExcelWriter, allowed_sheets: list[str]
    ) -> pd.ExcelWriter:
        desc = self.get_datapackage()
        settings = get_settings()

        bold = writer.book.add_format({"bold": True})  # type: ignore

        ws = writer.book.add_worksheet("package_description")  # type: ignore
        ws.set_column(2, 2, 40)
        ws.set_column(3, 3, 30)
        ws.write(2, 2, "Dataset", bold)
        ws.write(2, 3, desc["title"])
        ws.write(3, 2, "URL", bold)
        ws.write(3, 3, self.url)
        ws.write(4, 2, "Dataset description", bold)
        ws.write(4, 3, desc["description"])
        if "licenses" in desc:
            ws.write(5, 2, "Licence", bold)
            for n, licence in enumerate(desc["licenses"]):
                if "path" in licence:
                    ws.write_url(5, 3 + n, licence["path"], string=licence["title"])
        if "version" in desc:
            ws.write(6, 2, "Version", bold)
            ws.write(6, 3, self.get_current_version())

        row = 8

        if "contributors" in desc:
            ws.write(row, 2, "Contributors", bold)
            row += 1
            for contrib in desc["contributors"]:
                author = contrib.get("title", "")
                org = contrib.get("organization", "")
                if author and org:
                    credit = f"{author} ({org})"
                elif author:
                    credit = author
                else:
                    credit = org
                url = contrib.get("path", "")
                if url:
                    ws.write_url(row, 2, url, string=credit)
                else:
                    ws.write(row, 2, credit)
                row += 1

        if "sources" in desc:
            row += 1
            ws.write(row, 2, "Sources", bold)
            row += 1
            for source in desc["sources"]:
                title = source["title"]
                url = source.get("path", "")
                if url:
                    ws.write_url(row, 2, url, string=title)
                else:
                    ws.write(row, 2, title)
                row += 1

        row += 2
        ws.write(row, 2, "Sheet", bold)
        ws.write(row, 3, "Metadata", bold)
        ws.write(row, 4, "Sheet description", bold)
        row += 1

        # sort sheets in order

        ws.write_url(row, 2, "internal:data_description!A1", string="Data description")
        ws.write(row, 4, "Field descriptions and metadata for each sheet")
        row += 1

        for r in self.resources().values():
            if r.slug not in allowed_sheets:
                continue
            desc = r.get_resource()
            ws.write_url(row, 2, f"internal:{r.slug}!A1", string=desc["title"])
            ws.write(row, 4, desc["description"])
            row += 1

        row += 1

        ws.write_url(
            row,
            2,
            self.survey_url(),
            string=settings.credit_text,
        )

        return writer

    def get_composite_options(
        self,
        composite_type: Literal["xlsx", "sqlite", "json"],
    ) -> CompositeOptions:
        """
        Resolve composite inclusion, exclusion, modification, and render options.
        """
        configuration = self.extras.composite.for_format(composite_type)
        return configuration.resolve(self.resources())

    def build_excel(self, is_geodata: bool = False) -> None:
        """
        Build a single excel file for all resources
        """

        composite_options = self.get_composite_options("xlsx")
        if composite_options.render is False:
            rich.print("[red]Skipping Excel build[/red]")
            return

        allowed_resource_slugs = [
            x for x in composite_options.include if x not in composite_options.exclude
        ]

        sheets: dict[str, pd.DataFrame] = {}

        metadata_sheets: list[pd.DataFrame] = []

        for slug, resource in self.resources().items():
            if slug in allowed_resource_slugs:
                mdf = resource.get_metadata_df()
                mdf["resource"] = slug
                metadata_sheets.append(mdf)

        metadata_df = pd.concat(metadata_sheets)

        sheets["data_description"] = metadata_df

        for slug, resource in self.resources().items():
            if slug in allowed_resource_slugs:
                sheets[slug] = resource.get_df()

        excel_path = self.build_path() / f"{self.slug}.xlsx"

        writer = pd.ExcelWriter(excel_path)
        writer = self.build_coversheet(writer, allowed_sheets=allowed_resource_slugs)
        text_wrap = writer.book.add_format({"text_wrap": True})  # type: ignore

        for sheet_name, df in sheets.items():
            short_sheet_name = sheet_name[-31:]  # only allow 31 characters
            # if geometry is column - remove it
            if is_geodata and "geometry" in df.columns:
                df = df.drop(columns=["geometry"])
            df.to_excel(writer, sheet_name=short_sheet_name, index=False)

            for column in df:
                column_length = max(df[column].astype(str).map(len).max(), len(column))  # type: ignore
                column_length += 4

                col_idx = df.columns.get_loc(column)
                if column_length <= 50:
                    writer.sheets[short_sheet_name].set_column(
                        col_idx, col_idx, column_length
                    )
                else:  # word wrap
                    writer.sheets[short_sheet_name].set_column(
                        col_idx, col_idx, 50, text_wrap
                    )

        writer.close()

    def build_sqlite(self, is_geodata: bool = False) -> None:
        """
        Create a composite sqlite file for all resources
        with metadata as a seperate table.
        """

        sheets = {}
        metadata: list[pd.DataFrame] = []

        composite_options = self.get_composite_options("sqlite")
        if composite_options.render is False:
            rich.print("[red]Skipping sqlite build[/red]")
            return

        allowed_resource_slugs = [
            x for x in composite_options.include if x not in composite_options.exclude
        ]

        for slug, resource in self.resources().items():
            if slug not in allowed_resource_slugs:
                continue
            df = resource.get_df()
            if is_geodata and "geometry" in df.columns:
                df = df.drop(columns=["geometry"])
            sheets[slug] = df
            meta_df = resource.get_metadata_df()
            meta_df["resource"] = slug
            metadata.append(meta_df)

        sheets["data_description"] = pd.concat(metadata)

        sqlite_file = self.build_path() / f"{self.slug}.sqlite"

        if sqlite_file.exists():
            sqlite_file.unlink()
        con = sqlite3.connect(sqlite_file)
        for name, df in sheets.items():
            df.to_sql(name, con, index=False)
        con.close()

    def build_composite_json(self, is_geodata: bool = False) -> None:
        """
        This builds a composite json file that inlines the data as json.
        It can have less resources than the total, and some modifiers on the data.
        """

        datapackage = self.get_datapackage()
        composite_options = self.get_composite_options("json")
        if composite_options.render is False:
            rich.print("[red]Skipping json build[/red]")
            return

        allowed_resource_slugs = [
            x for x in composite_options.include if x not in composite_options.exclude
        ]

        datapackage["resources"] = [
            x.get_resource(inline_data=True, is_geodata=is_geodata)
            for x in self.resources().values()
            if x.slug in allowed_resource_slugs
        ]

        del datapackage["custom"]

        def modify_item_in_row(
            row: dict[str, Any],
            column: str,
            operation: Callable[[Any], Any],
        ) -> dict[str, Any]:
            """
            Modify one row in a JSON array.
            """
            if column in row:
                row[column] = operation(row[column])
            return row

        t = TypeVar("t", str, float)

        def convert_to_array_from_comma(value: t) -> list[t]:
            if isinstance(value, str):
                return value.split(",")
            else:
                return [value]

        # update json with any modifications
        # for instance splitting comma seperated fields to arrays
        for resource_slug, modify_maps in composite_options.modify.items():
            for column, modify_type in modify_maps.items():
                # split specified columns to arrays and update the schema
                if modify_type == "comma-to-array":
                    for resource in datapackage["resources"]:
                        assert "data" in resource
                        if resource["name"] == resource_slug:
                            col_to_position = {
                                y["name"]: x
                                for x, y in enumerate(resource["schema"]["fields"])
                            }
                            schema_field = resource["schema"]["fields"][
                                col_to_position[column]
                            ]
                            schema_field["type"] = "array"
                            schema_field["example"] = [schema_field["example"]]
                            if "comma seperated" in schema_field["description"]:
                                schema_field["description"] = schema_field[
                                    "description"
                                ].replace("comma seperated", "array")
                            resource["data"] = [
                                modify_item_in_row(
                                    x, column, convert_to_array_from_comma
                                )
                                for x in resource["data"]
                            ]
                else:
                    raise ValueError(f"Unrecognised modify type {modify_type}")

        def custom_converter(value: object) -> list[Any] | None:
            if isinstance(value, np.ndarray):
                return list(value)
            return None

        with open(self.build_path() / f"{self.slug}.json", "w") as f:
            json.dump(datapackage, f, indent=4, default=custom_converter)

    def build_composites(self) -> None:
        """
        Create composite files for the datapackage
        """
        is_geodata = self.is_geodata()
        self.build_excel(is_geodata)
        self.build_sqlite(is_geodata)
        self.build_composite_json(is_geodata)

    def build_markdown(self) -> None:
        """
        Create composite files for the datapackage
        """

    def print_status(self) -> None:
        resources = list(self.resources().values())

        df = pd.DataFrame(
            {
                "Resource": [x.slug for x in resources],
                "Status": [make_color(*x.get_status()) for x in resources],
            }
        )

        data = self.get_datapackage()

        panel = PanelPrint(
            title=data["name"],
            subtitle="For more options `dataset --help`",
            padding=1,
            expand=False,
            width=200,
        )

        panel.print("")
        panel.print("[u]Data Package[/u]")
        panel.print("")
        panel.print(f"{data['title']}")
        panel.print("")
        panel.print("[u]Description[/u]")
        panel.print("")
        panel.print(data["description"])
        table = Table(header_style="bold blue", expand=False)
        table = df_to_table(df, table, show_index=False)
        panel.print("")
        panel.print("[u]Resource status[/u]")
        panel.print("")
        panel.print(table)
        panel.display()
