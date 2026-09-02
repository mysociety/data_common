from __future__ import annotations

from pathlib import Path

import pandas as pd
from frictionless import validate
from ruamel.yaml import YAML

from data_common.dataset.table_management import update_table_schema

DESCRIPTIONS = {
    "identifier": "Row identifier",
    "name": "Row name",
    "is_holding": "Whether the answer is a holding answer",
    "attachments": "List of attachments to the answer",
}


def field_types(schema: dict) -> dict[str, str]:
    """
    Map field names to their described type.
    """
    return {field["name"]: field["type"] for field in schema["fields"]}


def described_schema() -> dict:
    """
    Return a prior schema carrying a description for every column.
    """
    return {
        "fields": [
            {"name": name, "type": "string", "description": description}
            for name, description in DESCRIPTIONS.items()
        ]
    }


def write_parquet(path: Path) -> Path:
    """
    Write a parquet file holding the column shapes pandas cannot type alone.
    """
    frame = pd.DataFrame(
        {
            "identifier": [1, 2],
            "name": ["first", "second"],
            "is_holding": [True, False],
            "attachments": [[], ["one"]],
        }
    )
    frame.to_parquet(path)
    return path


def test_object_columns_are_described_by_their_values(tmp_path: Path) -> None:
    """
    Describe list and boolean columns by content rather than by dtype.
    """
    schema = update_table_schema(write_parquet(tmp_path / "data.parquet"), None)

    types = field_types(schema)

    assert types["attachments"] == "any"
    assert types["is_holding"] == "boolean"
    assert types["identifier"] == "integer"
    assert types["name"] == "string"


def test_described_parquet_passes_validation(tmp_path: Path) -> None:
    """
    Validate a parquet file against the schema generated for it.

    pandas types every object column as a string, but validation reads the
    file natively, so list and boolean columns previously failed against the
    schema describing them.
    """
    data_path = write_parquet(tmp_path / "data.parquet")
    resource_path = tmp_path / "data.resource.yaml"
    resource = {
        "name": "data",
        "path": data_path.name,
        "format": "parquet",
        "schema": update_table_schema(data_path, described_schema()),
    }
    YAML().dump(resource, resource_path)

    report = validate(str(resource_path)).to_dict()

    assert report["stats"]["errors"] == 0


def test_existing_descriptions_survive_retyping(tmp_path: Path) -> None:
    """
    Keep field descriptions when a field type is corrected.
    """
    data_path = write_parquet(tmp_path / "data.parquet")

    schema = update_table_schema(data_path, described_schema())

    attachments = next(f for f in schema["fields"] if f["name"] == "attachments")
    assert attachments["type"] == "any"
    assert attachments["description"] == "List of attachments to the answer"


def test_non_scalar_columns_claim_no_uniqueness(tmp_path: Path) -> None:
    """
    Leave uniqueness unclaimed for a column validation cannot key on.

    Every attachments value here is distinct, but validation records seen
    cells in a dict, and a numpy array is unhashable.
    """
    schema = update_table_schema(write_parquet(tmp_path / "data.parquet"), None)

    attachments = next(f for f in schema["fields"] if f["name"] == "attachments")
    assert attachments["constraints"]["unique"] is False


def test_columns_holding_blanks_are_given_no_enum(tmp_path: Path) -> None:
    """
    Skip the enum for a column with missing values.

    A missing number reads as a nan, and an enum holding a nan can never be
    satisfied, because a nan does not equal itself.
    """
    path = tmp_path / "gaps.parquet"
    pd.DataFrame(
        {
            "member": [1.0, None, 2.0],
            "house": ["Commons", "Commons", "Commons"],
        }
    ).to_parquet(path)

    schema = update_table_schema(path, None)

    fields = {field["name"]: field for field in schema["fields"]}
    assert "enum" not in fields["member"]["constraints"]
    assert fields["house"]["constraints"]["enum"] == ["Commons"]


def test_all_null_object_column_stays_a_string(tmp_path: Path) -> None:
    """
    Leave a column with no values to type as pandas described it.
    """
    path = tmp_path / "empty.parquet"
    pd.DataFrame({"empty": [None, None]}).to_parquet(path)

    schema = update_table_schema(path, None)

    assert field_types(schema)["empty"] == "string"
