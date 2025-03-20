from pathlib import Path
from typing import Any, Callable, Dict, TypedDict

import numpy as np
import pandas as pd
from pandas.io.json import build_table_schema


class TypedFieldSchema(TypedDict):
    name: str
    example: str | int | float
    constraints: dict[str, Any]
    description: str | None


class SchemaValidator(TypedDict):
    fields: list[TypedFieldSchema]


def expand_array(series: pd.Series) -> pd.Series:
    """
    This function takes in a series and returns a new series where any arrays have been expanded into separate rows.
    """
    # if any values are an np.ndarray - we need to convert them to a string to avoid a TypeError
    if any(isinstance(x, (list, tuple, np.ndarray)) for x in series):
        return series.apply(str)  # type: ignore
    return series


def is_unique(series: pd.Series) -> bool:
    """
    This function takes in a series and returns a boolean of whether or not all the values in the series are unique.
    """

    return len(series) == len(expand_array(series).astype(str).unique())


def get_example(series: pd.Series) -> str | int | float:
    try:
        str_series = series.dropna().apply(str)
        item = sorted(list(str_series))
    except ValueError:
        item = series
    if len(item) == 0:
        return ""
    if isinstance(item, dict):
        return str(item)
    if isinstance(item, pd.Series):
        item = item.iloc[0]
    else:
        item = str(item[0])
    if isinstance(item, bool):
        return str(item)
    if isinstance(item, float):
        return float(item)
    if isinstance(item, int):
        return int(item)
    return str(item)


def get_descriptions_from_schema(original_schema: SchemaValidator) -> dict[str, str]:
    """
    Returns a dictionary mapping field names to descriptions.
    """
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
            if isinstance(field["constraints"]["enum"], list):
                # sort the enum values
                non_none_enums = [
                    x for x in field["constraints"]["enum"] if x is not None
                ]
                field["constraints"]["enum"] = sorted(non_none_enums)
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
        data: SchemaValidator = build_table_schema(df, index=False, version=False)  # type: ignore
        data["fields"] = [
            cls.enhance_field(df, field, descriptions, enums)
            for field in data["fields"]
        ]
        return data


def update_table_schema(
    path: Path, existing_schema: SchemaValidator | None
) -> SchemaValidator:
    if path.suffix == ".csv":
        df = pd.read_csv(path)
    elif path.suffix == ".parquet":
        df = pd.read_parquet(path)
    else:
        raise ValueError(f"Unsupported file type {path.suffix}")

    # get columns that have less than 15 unique entries and have no blank entries

    def safe_unique(col: pd.Series) -> bool:
        # check nunique is under 15
        # if the series contains any items that is itsef an numpy array - we need to
        # convert it to a string to avoid a TypeError
        if any(isinstance(x, (list, tuple, np.ndarray)) for x in col):
            return False
        str_col = col.apply(str)
        return str_col.nunique() < 15 and not str_col.isnull().any()

    cols = df.apply(safe_unique)
    low_count_cols = df.columns.to_series()[cols].to_list()

    return Schema.get_table_schema(
        df,
        descriptions=(
            get_descriptions_from_schema(existing_schema) if existing_schema else {}
        ),
        enums={x: Schema.USE_UNIQUE for x in low_count_cols},
    )
