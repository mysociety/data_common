from pathlib import Path
from typing import Any, Callable, Dict, TypedDict

import pandas as pd
from pandas.io.json import build_table_schema


class TypedFieldSchema(TypedDict):
    name: str
    example: str | int | float
    constraints: dict[str, Any]
    description: str | None


class SchemaValidator(TypedDict):
    fields: list[TypedFieldSchema]


def is_unique(series: pd.Series) -> bool:
    return len(series) == len(series.unique())


def get_example(series: pd.Series) -> str | int | float:
    item = series.dropna()[0]
    if isinstance(item, float):
        return float(item)
    if isinstance(item, int):
        return int(item)
    return str(item)


def get_descriptions_from_schema(original_schema: SchemaValidator) -> dict[str, str]:
    fields = original_schema["fields"]
    return {
        x["name"]: x["description"]
        for x in fields
        if "description" in x and x["description"] is not None
    }


class EnumPlaceholder:
    def __init__(self, func: Callable[[pd.Series], list]):
        self.func = func

    def process(self, series: pd.Series) -> list:
        return self.func(series)


class Schema:
    USE_UNIQUE = EnumPlaceholder(lambda series: series.unique().tolist())

    @classmethod
    def enhance_field(
        cls,
        df: pd.DataFrame,
        field: TypedFieldSchema,
        descriptions: dict[str, str],
        enums: dict[str, Any],
    ) -> TypedFieldSchema:
        col = df[field["name"]]
        field["description"] = descriptions.get(field["name"], None)
        field["constraints"] = {"unique": is_unique(col)}
        if (example := get_example(col)) is not None:
            field["example"] = example
        if field["name"] in enums:
            enum_value = enums[field["name"]]
            if isinstance(enum_value, list):
                field["constraints"]["enum"] = enum_value
            if isinstance(enum_value, EnumPlaceholder):
                field["constraints"]["enum"] = enum_value.process(col)
        return field

    @classmethod
    def get_table_schema(
        cls,
        df: pd.DataFrame,
        descriptions: dict[str, str] = {},
        *,
        enums: Dict[str, EnumPlaceholder | list[Any]] = {},
    ) -> SchemaValidator:
        """
        Produce a table data schema for the dataframe
        https://specs.frictionlessdata.io/table-schema/
        """
        data: SchemaValidator = build_table_schema(df, index=False, version=False)
        data["fields"] = [
            cls.enhance_field(df, field, descriptions, enums)
            for field in data["fields"]
        ]
        return data


def update_table_schema(
    path: Path, existing_schema: SchemaValidator | None
) -> SchemaValidator:
    df = pd.read_csv(path)
    return Schema.get_table_schema(
        df,
        descriptions=get_descriptions_from_schema(existing_schema)
        if existing_schema
        else {},
        enums={
            "section": Schema.USE_UNIQUE,
        },
    )