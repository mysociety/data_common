import hashlib
import importlib
import io
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import warnings
from dataclasses import dataclass
from pathlib import Path
from shutil import copyfile
from typing import Any, Callable, Dict, Literal, TypedDict, TypeVar, cast
from urllib.parse import urlencode
import geopandas as gpd

import pandas as pd
import pytest
import rich
import xlsxwriter
import re

from frictionless import Schema, describe, validate
from pyparsing import any_open_tag
from rich.markdown import Markdown
from rich.table import Table
from ruamel.yaml import YAML

from data_common.db import duck_query

from .jekyll_management import render_jekyll
from .rich_assist import PanelPrint, df_to_table
from .settings import get_settings
from .table_management import SchemaValidator, update_table_schema
from .version_management import (
    bump_version,
    is_valid_semver,
    parse_semver,
    semver_is_higher,
)


def diff_dicts(a: dict, b: dict, missing=KeyError):
    """
    Return a dictionary of keys and values that are difference
    between two dictionaries, a and b, which both can contain dictionaries as values.

    """
    diff = {}
    for key in set(a.keys()).union(b.keys()):
        try:
            a_value = a[key]
        except missing:
            a_value = None
        try:
            b_value = b[key]
        except missing:
            b_value = None
        if a_value != b_value:
            diff[key] = (a_value, b_value)
    return diff


version_rules = (
    Literal["MAJOR"] | Literal["MINOR"] | Literal["PATCH"] | Literal["INITIAL"]
)


class CompositeOptions(TypedDict):
    include: list[str]
    exclude: list[str]
    modify: dict[str, dict[str, str]]
    render: str


class ResourceStub(TypedDict):
    name: str
    title: str
    licence: dict[str, str]


alert_colors = Literal["red"] | Literal["green"] | Literal["orange"] | Literal["blue"]
ValidationErrors = list[tuple[str, alert_colors]]


def make_color(item: str, color: alert_colors) -> str:
    return f"[{color}]{item}[/{color}]"


def color_print(item: str, color: alert_colors, new_line: bool = True) -> None:
    rich.print(make_color(item, color), end="\n" if new_line else " ")


@dataclass
class DataResource:
    path: Path

    @property
    def slug(self) -> str:
        return self.path.stem

    def get_order(self) -> int:
        """
        Get a sheet order if one has been set
        """
        desc = self.get_resource()
        return desc.get("_sheet_order", 999)

    @property
    def resource_path(self) -> Path:
        """
        Path to a yaml file describing this resource
        """
        return self.path.parent / (self.slug + ".resource.yaml")

    @property
    def has_resource_yaml(self) -> bool:
        return self.resource_path.exists()

    def validate_descriptions(self) -> str:
        """
        Enforce checks on optional title and description parameters
        """
        if self.has_resource_yaml is False:
            return "Missing schema"

        problems: list[tuple[str, str]] = []

        desc = self.get_resource()
        if not desc["title"]:
            problems.append(("title", "resource"))
        if not desc["description"]:
            problems.append(("description", "resource"))

        for f in desc["schema"]["fields"]:
            if not f["description"]:
                problems.append(("description", f["name"]))

        if len(problems) == 0:
            return ""
        else:
            problems_str = [" for ".join(x) for x in problems]
            return "Missing: " + ", ".join(problems_str)

    def get_status(self) -> tuple[str, alert_colors]:
        """
        Check for errors in a resource
        """
        if not self.has_resource_yaml:
            return "No resource file", "red"
        if desc_error := self.validate_descriptions():
            return desc_error, "red"
        valid_check = validate(self.resource_path)
        if valid_check["stats"]["errors"] > 0:
            return valid_check["tasks"][0]["errors"], "red"
        return "Valid resource", "green"

    def get_df(self) -> pd.DataFrame:
        """
        Get a dataframe of the resource
        """
        # if is csv
        if self.path.suffix == ".csv":
            return pd.read_csv(self.path)
        # if parquet
        elif self.path.suffix == ".parquet":
            return pd.read_parquet(self.path)
        else:
            raise ValueError(f"Unhandled file type {self.path.suffix}")

    def get_resource(self, inline_data: bool = False) -> dict[str, Any]:
        if self.has_resource_yaml:
            yaml = YAML(typ="safe")
            with open(self.resource_path, "r") as f:
                resource = yaml.load(f)
            if inline_data:
                resource["data"] = (
                    self.get_df().fillna(value="").to_dict(orient="records")
                )
                resource["format"] = "json"
                del resource["scheme"]
                del resource["path"]
            return resource

        return {}

    def get_metadata_df(self) -> pd.DataFrame:
        if self.has_resource_yaml is False:
            raise ValueError("Trying to get metadata for {self.slug}, but not present.")
        resource = self.get_resource()
        df = pd.DataFrame(resource["schema"]["fields"])
        df["unique"] = df["constraints"].apply(
            lambda x: "Yes" if x.get("unique", False) else "No"
        )
        df["options"] = df["constraints"].apply(
            lambda x: ", ".join([str(x) for x in x.get("enum", [])])
        )
        df = df.drop(columns=["constraints"]).rename(columns={"name": "column"})
        df = df[["column", "description", "type", "example", "unique", "options"]]
        return df

    def get_schema_from_file(
        self, existing_schema: SchemaValidator | None
    ) -> SchemaValidator:
        return update_table_schema(self.path, existing_schema)

    def rebuild_yaml(self, is_geodata: bool = False):
        """
        Recreate yaml file from source file, preserving any custom values from previously existing yaml file
        """
        from frictionless.resource.resource import Resource

        existing_desc = self.get_resource()
        desc = describe(self.path)
        desc.update(existing_desc)

        desc["schema"] = self.get_schema_from_file(existing_desc.get("schema", None))
        desc["path"] = self.path.name

        # if geodata - drop geometry example from schema
        if is_geodata:
            new_fields = []
            for f in desc["schema"]["fields"]:
                if f["name"] == "geometry":
                    f["example"] = ""
                new_fields.append(f)
            desc["schema"]["fields"] = new_fields

        # ensure a blank title and description
        new_dict = {"title": None, "description": None, "custom": {}}

        new_dict.update(desc.to_dict())

        resource_path = self.path
        # resource must be csv
        if resource_path.suffix not in [".csv", ".parquet"]:
            raise ValueError(
                "Resource must be csv or paraquet, update this function if extending past that."
            )

        # get number of rows in resource

        rows = duck_query(
            "SELECT COUNT(*) FROM {{ file_path }}", file_path=resource_path
        ).int()

        # update number of rows in resource (custom)
        new_dict["custom"]["row_count"] = rows

        # get md5 hash of resource
        with open(resource_path, "rb") as f:
            md5 = hashlib.md5(f.read()).hexdigest()
        new_dict["hash"] = md5

        yaml = YAML()
        yaml.default_flow_style = False

        # dump yaml to a textio stream
        with io.StringIO() as f:
            yaml.dump(new_dict, f)
            yaml_str = f.getvalue()

        # horrible little patch to always put a quote around No
        yaml_str = yaml_str.replace(": No\n", ": 'No'\n")
        yaml_str = yaml_str.replace(": Yes\n", ": 'Yes'\n")

        # and in enums
        yaml_str = yaml_str.replace("- No\n", "- 'No'\n")
        yaml_str = yaml_str.replace("- Yes\n", "- 'Yes'\n")
        yaml_str = yaml_str.replace("- no\n", "- 'no'\n")
        yaml_str = yaml_str.replace("- yes\n", "- 'yes'\n")

        with open(self.resource_path, "w") as f:
            f.write(yaml_str)
        print(f"Updated config for {self.slug} to {self.resource_path}")


@dataclass
class DataPackage:
    path: Path

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
        Check the tests directory for a pytest file named 'test_{package.slug}.py'
        If this exists, run it, if not, return None.
        if tests pass, return True, if not, return False.

        Can specify multiple test filenames as "custom": "tests": ["test_1", "test_2"]
        in the datapackage yml.

        """
        old_stdout = None
        test_dir = self.path.parent.parent.parent / "tests"
        desc = self.get_datapackage()
        tests = desc["custom"].get("tests", [])
        tests = [x + ".py" for x in tests]
        if tests == []:
            if (test_dir / f"test_{self.slug}.py").exists():
                tests.append(f"test_{self.slug}.py")
        paths = [test_dir / x for x in tests]
        if quiet is False:
            rich.print("[blue]Running tests[/blue]")
        elif quiet is True:
            old_stdout = sys.stdout
            sys.stdout = open(os.devnull, "w")
        results = [
            pytest.main(["--quiet"] + [str(test_path)])
            for test_path in paths
            if test_path.exists()
        ]
        if quiet is True:
            sys.stdout = old_stdout
        if results:
            return max(results) == 0
        else:
            rich.print(
                "[red]A test path is configured, but the file does not exist[/red]"
            )
            return True  # Ok with this, with the warning

    def build_from_function(self):
        """
        Function to build data from a function specified in a module.
        """
        desc = self.get_datapackage()
        build_module = desc.get("custom", {}).get("build", "")
        build_module = build_module.strip() if build_module else ""
        if not build_module:
            rich.print(
                "[red]No build command or python path specified in custom.build in the yaml[/red]"
            )
            return None
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
        auto_ban: list[str] = [],
        publish: bool = False,
    ):
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
                return None
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
            render_jekyll()

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
            return MAJOR, "Datapackage name changed from {p_name} to {c_name}"
        if (p_identifier := previous_data.get("identifier")) != (
            c_identifier := current_data.get("identifier")
        ):
            return (
                MAJOR,
                "Datapackage identifier changed from {p_identifier} to {c_identifier}",
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
            current_resource = [
                x
                for x in current_data["resources"]
                if x["name"] == previous_resource["name"]
            ][0]
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
                    current_field = [
                        x
                        for x in current_schema_fields
                        if x["name"] == previous_field["name"]
                    ][0]
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
    ):
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
                raise ValueError(f"Package is not valid, cannot update version.")

            # increment the version in the yaml and update change log
            custom = desc["custom"]
            change_log = custom.get("change_log", {})
            change_log[new_semver] = update_message
            custom["change_log"] = change_log
            if dry_run:
                rich.print("[yellow]Dry run, not updating.[/yellow]")
                rich.print(
                    f"[blue]Would update to version {new_semver} because of {update_message}[/blue]"
                )
            else:
                self.update_yaml({"version": new_semver, "custom": custom})
                self.store_version()
                rich.print(f"{self.slug} version bumped to [green]{new_semver}[/green]")
                if publish:
                    self.rebuild_all_resources()
                    self.build_package()
                    self.build_missing_previous_versions()
                    render_jekyll()
        else:
            print(f"{new_semver} is not higher than {version} or is 0.1.0.")

    def store_version(self):
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

    def update_yaml(self, new_values: dict[str, Any]):
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
        build_path = get_settings()["publish_dir"] / "data" / self.slug / version
        if build_path.exists() is False:
            build_path.mkdir(parents=True, exist_ok=True)
        return build_path

    def __post_init__(self):
        if self.datapackage_path.exists() is False:
            raise ValueError(f"No datapackage.yaml found in {self.path}")

    def resources(self) -> dict[str, DataResource]:
        # a resource can be a csv or a parquet file
        resources = [DataResource(path=x) for x in self.path.glob("*.csv")]
        resources += [DataResource(path=x) for x in self.path.glob("*.parquet")]

        # check there aren't any csvs and paraquets with the same name
        if len(set([x.path.stem for x in resources])) != len(resources):
            raise ValueError(
                f"Found multiple resources with the same name in {self.path}"
            )

        resources.sort(key=lambda x: x.slug)
        resources.sort(key=lambda x: x.get_order())
        return {x.slug: x for x in resources}

    @property
    def resource_count(self) -> int:
        return len(self.resources())

    @property
    def url(self) -> str:
        return (
            get_settings()["publish_url"]
            + "datasets/"
            + self.slug.replace("_", "-")
            + "/"
        )

    def rebuild_resource(self, slug: str):
        resource = self.resources()[slug]
        resource.rebuild_yaml()

    def rebuild_all_resources(self):
        is_geodata = self.is_geodata()
        for resource in self.resources().values():
            resource.rebuild_yaml(is_geodata=is_geodata)

    def is_geodata(self) -> bool:
        desc = self.get_datapackage()
        return desc["custom"].get("is_geodata", False)

    def get_datapackage(self) -> dict[str, Any]:
        yaml = YAML(typ="safe")
        with open(self.datapackage_path, "r"):
            return yaml.load(self.datapackage_path)

    def validate(self, quiet: bool = False) -> ValidationErrors:
        desc = self.get_datapackage()
        validation_errors: ValidationErrors = []
        if not desc.get("description", ""):
            validation_errors.append(("Missing package description", "red"))
        if not desc.get("title", ""):
            validation_errors.append(("Missing package title", "red"))
        if not desc.get("licenses", ""):
            validation_errors.append(("Missing package licence", "red"))
        if self.test_package(quiet) is False:
            validation_errors.append(("Tests failed", "red"))
        for r in self.resources().values():
            if r.get_status()[1] == "red":
                validation_errors.append((f"Invalid resource {r.slug}", "red"))
        return validation_errors

    def past_versions(self):
        """
        get a list of previous versions as avaliable in the versions folder
        """
        versions = []
        for version in self.path.glob("versions/*"):
            if version.is_dir():
                versions.append(version.name)
        return versions

    def build_missing_previous_versions(self):
        """
        Where there are previous versions in data/packages but not rendered to
        docs/data/packages, build them.
        """

        for v in self.past_versions():
            build_path = self.build_path(v)
            if (build_path / "datapackage.json").exists() is False:
                color_print(f"Building missing {self.slug} version {v}", "red")
                previous = self.__class__(self.path / "versions" / v)
                previous.build_package()

    def build_package(self):
        """
        Build package files and move to jekyll directory
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

    def check_build_integrity(self):
        """
        run the validator against the data pacakge
        """

        with warnings.catch_warnings():
            warnings.filterwarnings("ignore")
            valid_results = validate(
                self.build_path() / "datapackage.json", type="package"
            )
        if valid_results["stats"]["errors"] > 0:
            raise ValueError(valid_results)

    def copy_resources(self):
        """
        Copy the CSV/parquet over and create the opposite item.
        Use DUCKDB to make the conversion robust for larger files.
        """

        desc = self.get_datapackage()
        formats = desc.get("custom", {}).get("formats", {})
        csv_value = formats.get("csv", True)
        parquet_value = formats.get("parquet", True)
        geojson_value = formats.get("geojson", False)
        geopackage_value = formats.get("gpkg", False)

        csv_copy_query = """
        copy (select * from {{ source }}) to {{ dest }} (format PARQUET);
        """
        exclude = ""
        if desc["custom"].get("is_geodata", False):
            exclude = "EXCLUDE geometry"

        parquet_copy_query = """
        copy (select * {{ exclude }} from {{ source }}) to {{ dest }} (HEADER, DELIMITER ',');
        """

        for r in self.resources().values():
            # need to have seperate handling for csv and paraquet
            if r.path.suffix == ".csv":
                if csv_value:
                    copyfile(r.path, self.build_path() / r.path.name)
                if parquet_value:
                    parquet_file = self.build_path() / (r.path.stem + ".parquet")
                    duck_query(csv_copy_query, source=r.path, dest=parquet_file).run()
                if geojson_value or geopackage_value:
                    raise ValueError(
                        "Writing to geojson/geopackage from csv source not supported. Use parquet internally."
                    )
            elif r.path.suffix == ".parquet":
                if parquet_value:
                    copyfile(r.path, self.build_path() / r.path.name)
                if csv_value:
                    csv_file = self.build_path() / (r.path.stem + ".csv")
                    duck_query(
                        parquet_copy_query,
                        exclude=exclude,
                        source=r.path,
                        dest=csv_file,
                    ).run()
                if geojson_value:
                    geojson_path = self.build_path() / (r.path.stem + ".geojson")
                    gdf = gpd.read_parquet(r.path)
                    gdf.to_file(geojson_path, driver="GeoJSON")
                if geopackage_value:
                    geopackage_path = self.build_path() / (r.path.stem + ".gpkg")
                    gdf = gpd.read_parquet(r.path)
                    gdf.to_file(geopackage_path, driver="GPKG")

    def get_datapackage_order(self) -> int:
        """
        Get any priority order between the datasets
        """
        datapackage = self.get_datapackage()
        if "custom" not in datapackage:
            datapackage["custom"] = {}
            if "dataset_order" not in datapackage["custom"]:
                datapackage["custom"]["dataset_order"] = 999
        return datapackage["custom"]["dataset_order"]

    def get_current_datapackage_json(self) -> dict[str, Any]:
        """
        Get a dictionary representation of the current datapackage
        """
        datapackage = self.get_datapackage()
        datapackage["resources"] = [x.get_resource() for x in self.resources().values()]
        if "custom" not in datapackage:
            datapackage["custom"] = {}
            if "dataset_order" not in datapackage["custom"]:
                datapackage["custom"]["dataset_order"] = 999
        return datapackage

    def build_json(self):
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
        desc = self.get_datapackage()
        settings = get_settings()
        default_survey_url = settings["credit_url"]
        specific_alchemer: str | None = (
            desc.get("custom", {}).get("download_options", {}).get("survey", None)
        )
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

        bold = writer.book.add_format({"bold": True})

        ws = writer.book.add_worksheet("package_description")
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

        for r in self.resources().values():
            if r.slug not in allowed_sheets:
                continue
            desc = r.get_resource()
            metadata_sheet = f"{r.slug}_metadata"[-31:]
            ws.write_url(row, 2, f"internal:{r.slug}!A1", string=desc["title"])
            ws.write_url(
                row,
                3,
                f"internal:{metadata_sheet}!A1",
                string="View column information",
            )
            ws.write(row, 4, desc["description"])
            row += 1

        row += 1

        ws.write_url(
            row,
            2,
            self.survey_url(),
            string=settings["credit_text"],
        )

        return writer

    def get_composite_options(
        self, composite_type: Literal["xlsx"] | Literal["sqlite"] | Literal["json"]
    ) -> CompositeOptions:
        """
        Return the composite inclusion/exclusion options for a specific composite type
        This allows certain resources to be excluded from certain composites.
        """

        desc = self.get_datapackage()

        default_options = {
            "include": "all",
            "exclude": "None",
            "modify": {},
            "render": True,
        }

        update = (
            desc.get("custom", {})
            .get("composite", {})
            .get(composite_type, default_options)
        )

        composite_options = default_options
        composite_options.update(update)

        if composite_options["include"] == "all":
            composite_options["include"] = list(self.resources().keys())
        if composite_options["exclude"] == "none":
            composite_options["exclude"] = []

        composite_options = cast(CompositeOptions, composite_options)

        return composite_options

    def build_excel(self):
        """
        Build a single excel file for all resources
        """

        composite_options = self.get_composite_options("xlsx")
        if composite_options["render"] is False:
            rich.print("[red]Skipping Excel build[/red]")
            return None

        allowed_resource_slugs = [
            x
            for x in composite_options["include"]
            if x not in composite_options["exclude"]
        ]

        sheets: dict[str, pd.DataFrame] = {}

        for slug, resource in self.resources().items():
            if slug in allowed_resource_slugs:
                sheets[slug] = resource.get_df()
                sheets[slug + "_metadata"] = resource.get_metadata_df()

        excel_path = self.build_path() / f"{self.slug}.xlsx"

        writer = pd.ExcelWriter(excel_path)
        writer = self.build_coversheet(writer, allowed_sheets=allowed_resource_slugs)
        text_wrap = writer.book.add_format({"text_wrap": True})

        for sheet_name, df in sheets.items():
            short_sheet_name = sheet_name[-31:]  # only allow 31 characters
            # if geometry is column - remove it
            if "geometry" in df.columns:
                df = df.drop(columns=["geometry"])
            df.to_excel(writer, sheet_name=short_sheet_name, index=False)

            for column in df:
                column_length = max(df[column].astype(str).map(len).max(), len(column))
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

        writer.save()

    def build_sqlite(self):
        """
        Create a composite sqlite file for all resources
        with metadata as a seperate table.
        """

        sheets = {}
        metadata: list[pd.DataFrame] = []

        composite_options = self.get_composite_options("sqlite")
        if composite_options["render"] is False:
            rich.print("[red]Skipping sqlite build[/red]")
            return None

        allowed_resource_slugs = [
            x
            for x in composite_options["include"]
            if x not in composite_options["exclude"]
        ]

        for slug, resource in self.resources().items():
            if slug not in allowed_resource_slugs:
                continue
            sheets[slug] = resource.get_df()
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

    def build_composite_json(self):
        """
        This builds a composite json file that inlines the data as json.
        It can have less resources than the total, and some modifiers on the data.
        """

        datapackage = self.get_datapackage()
        composite_options = self.get_composite_options("json")
        if composite_options["render"] is False:
            rich.print("[red]Skipping json build[/red]")
            return None

        allowed_resource_slugs = [
            x
            for x in composite_options["include"]
            if x not in composite_options["exclude"]
        ]

        datapackage["resources"] = [
            x.get_resource(inline_data=True)
            for x in self.resources().values()
            if x.slug in allowed_resource_slugs
        ]

        del datapackage["custom"]

        def modify_item_in_row(row: dict, column: str, operation: Callable[[Any], Any]):
            """Modify a row in a json array"""
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
        for resource_slug, modify_maps in composite_options["modify"].items():
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

        with open(self.build_path() / f"{self.slug}.json", "w") as f:
            json.dump(datapackage, f, indent=4)

    def build_composites(self):
        """
        Create composite files for the datapackage
        """
        self.build_excel()
        self.build_sqlite()
        self.build_composite_json()

    def build_markdown(self):
        """
        Create composite files for the datapackage
        """
        ...

    def print_status(self):
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
