from __future__ import annotations

import hashlib
import io
import re
from pathlib import Path
from typing import Any, Literal, NamedTuple

import pandas as pd
from frictionless import describe, validate
from ruamel.yaml import YAML

from data_common.db import duck_query

from .table_management import SchemaValidator, update_table_schema

AlertColour = Literal["red", "green", "orange", "blue"]


class ResourceStatus(NamedTuple):
    """
    Pair a human-readable resource status with its display colour.
    """

    message: str
    colour: AlertColour


class MissingDescription(NamedTuple):
    """
    Identify a missing metadata field and the item it describes.
    """

    field: str
    item: str


class DataResource:
    """
    Read, validate, and rebuild one dataset resource and its YAML metadata.
    """

    def __init__(self, path: Path) -> None:
        self.path = path

    @property
    def slug(self) -> str:
        """
        Return the resource filename stem.
        """
        return self.path.stem

    def get_order(self, native_order: int = 999) -> int:
        """
        Return the configured sheet order or the supplied default.
        """
        description = self.get_resource()
        old_style = description.get("_sheet_order")
        if old_style is not None:
            return int(old_style)
        return int(description.get("custom", {}).get("dataset_order", native_order))

    @property
    def resource_path(self) -> Path:
        """
        Return the YAML metadata path for this resource.
        """
        return self.path.parent / f"{self.slug}.resource.yaml"

    @property
    def has_resource_yaml(self) -> bool:
        """
        Return whether YAML metadata exists for this resource.
        """
        return self.resource_path.exists()

    def validate_descriptions(self) -> str:
        """
        Return a summary of missing resource and field descriptions.
        """
        if not self.has_resource_yaml:
            return "Missing schema"

        problems: list[MissingDescription] = []
        description = self.get_resource()
        if not description["title"]:
            problems.append(MissingDescription("title", "resource"))
        if not description["description"]:
            problems.append(MissingDescription("description", "resource"))

        for field in description["schema"]["fields"]:
            if not field["description"]:
                problems.append(MissingDescription("description", field["name"]))

        if not problems:
            return ""
        details = [f"{problem.field} for {problem.item}" for problem in problems]
        return "Missing: " + ", ".join(details)

    def get_status(self) -> ResourceStatus:
        """
        Validate the resource and return its display status.
        """
        if not self.has_resource_yaml:
            return ResourceStatus("No resource file", "red")
        if description_error := self.validate_descriptions():
            return ResourceStatus(description_error, "red")
        validation = validate(self.resource_path).to_dict()
        if validation["stats"]["errors"] > 0:
            tasks = validation.get("tasks", [])
            errors = validation.get("errors", [])
            details = tasks[0].get("errors", []) if tasks else errors
            return ResourceStatus(
                str(details or "Resource validation failed"),
                "red",
            )
        return ResourceStatus("Valid resource", "green")

    def get_df(self) -> pd.DataFrame:
        """
        Load the resource into a dataframe.
        """
        if self.path.suffix == ".csv":
            return pd.read_csv(self.path)
        if self.path.suffix == ".parquet":
            return pd.read_parquet(self.path)
        raise ValueError(f"Unhandled file type {self.path.suffix}")

    def get_resource(
        self,
        inline_data: bool = False,
        is_geodata: bool = False,
    ) -> dict[str, Any]:
        """
        Load resource YAML, optionally embedding source records as JSON.
        """
        if not self.has_resource_yaml:
            return {}

        with self.resource_path.open() as stream:
            resource: dict[str, Any] = YAML(typ="safe").load(stream)
        if inline_data:
            dataframe = self.get_df()
            if is_geodata and "geometry" in dataframe.columns:
                dataframe = dataframe.drop(columns=["geometry"])
            resource["data"] = dataframe.fillna(value="").to_dict(orient="records")
            resource["format"] = "json"
            resource.pop("scheme", None)
            resource.pop("path", None)
        return resource

    def get_metadata_df(self) -> pd.DataFrame:
        """
        Return field metadata formatted for composite output.
        """
        if not self.has_resource_yaml:
            raise ValueError(
                f"Trying to get metadata for {self.slug}, but not present."
            )
        resource = self.get_resource()
        dataframe = pd.DataFrame(resource["schema"]["fields"])
        dataframe["unique"] = dataframe["constraints"].apply(
            lambda value: "Yes" if value.get("unique", False) else "No"
        )
        dataframe["options"] = dataframe["constraints"].apply(
            lambda value: ", ".join(str(item) for item in value.get("enum", []))
        )
        dataframe = dataframe.drop(columns=["constraints"]).rename(
            columns={"name": "column"}
        )
        return dataframe[
            ["column", "description", "type", "example", "unique", "options"]
        ]

    def get_schema_from_file(
        self,
        existing_schema: SchemaValidator | None,
    ) -> SchemaValidator:
        """
        Infer a resource schema while preserving compatible existing metadata.
        """
        return update_table_schema(self.path, existing_schema)

    def rebuild_yaml(self, is_geodata: bool = False) -> None:
        """
        Rebuild resource YAML while preserving existing custom values.
        """
        existing_description = self.get_resource()
        description = describe(self.path).to_dict()
        description.update(existing_description)
        description["schema"] = self.get_schema_from_file(
            existing_description.get("schema")
        )
        description["path"] = self.path.name

        if is_geodata:
            for field in description["schema"]["fields"]:
                if field["name"] == "geometry":
                    field["example"] = ""

        resource = {"title": None, "description": None, "custom": {}}
        resource.update(description)

        if self.path.suffix not in {".csv", ".parquet"}:
            raise ValueError("Resource must be CSV or Parquet")

        rows = duck_query(
            "SELECT COUNT(*) FROM {{ file_path }}",
            file_path=self.path,
        ).int()
        resource["custom"]["row_count"] = rows
        resource["hash"] = hashlib.md5(
            self.path.read_bytes(),
            usedforsecurity=False,
        ).hexdigest()

        yaml = YAML()
        yaml.default_flow_style = False
        with io.StringIO() as stream:
            yaml.dump(resource, stream)
            yaml_text = stream.getvalue()

        replacements = {
            ": No\n": ": 'No'\n",
            ": Yes\n": ": 'Yes'\n",
            "- No\n": "- 'No'\n",
            "- Yes\n": "- 'Yes'\n",
            "- no\n": "- 'no'\n",
            "- yes\n": "- 'yes'\n",
        }
        for source, destination in replacements.items():
            yaml_text = yaml_text.replace(source, destination)
        yaml_text = re.sub(
            r"example: (\d{2}:\d{2})",
            r'example: "\1"',
            yaml_text,
        )

        self.resource_path.write_text(yaml_text)
        print(f"Updated config for {self.slug} to {self.resource_path}")
