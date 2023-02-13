import duckdb
from typing import Any
import jinja2
from pathlib import Path
from functools import lru_cache
import toml
import pandas as pd
from typing import Any


@lru_cache
def get_settings(toml_file: str = "pyproject.toml") -> dict:
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

    data = toml.load(settings_file)["tool"]["duck"]
    return data


class DuckResponse:
    def __init__(self, response: duckdb.DuckDBPyConnection):
        self.response = response

    def __iter__(self):
        return iter(self.response.fetchall())

    def df(self) -> pd.DataFrame:
        return self.response.df()

    def fetchone(self) -> Any:
        return self.response.fetchone()[0]  # type: ignore

    def fetch_df(self) -> pd.DataFrame:
        return self.response.df()

    def fetch_int(self) -> int:
        return int(self.fetchone())

    def fetch_bool(self) -> bool:
        return bool(self.fetchone())

    def fetch_float(self) -> float:
        return float(self.fetchone())

    def fetch_str(self) -> str:
        return str(self.fetchone())

    def int(self) -> int:
        return self.fetch_int()

    def str(self) -> str:
        return self.fetch_str()

    def bool(self) -> bool:
        return self.fetch_bool()

    def float(self) -> float:
        return self.fetch_float()


def duck_query(query: str | Path, **kwargs: Any) -> DuckResponse:
    """
    Helper function to execute a query using duckdb.
    """

    ddb = duckdb.connect(":memory:")

    # if the query is a path, read it in
    if isinstance(query, Path) or query.endswith(".sql"):
        path = Path(query)
        if not path.exists():
            query_path = get_settings()["query_dir"]
            path = Path(query_path, query)
            if not path.exists():
                raise ValueError(f"Could not find query file {query}")
        query = path.read_text()

    def wrap_str(s: str) -> str:
        return f"'{s}'"

    def process_kwarg(key: str, value: Any) -> Any:
        # convert path to string in single quotes
        if isinstance(value, Path):
            return wrap_str(str(value))
        # register any dataframes passed in
        if isinstance(value, pd.DataFrame):
            ddb.register(key, value)
            return key

        return value

    template = jinja2.Environment().from_string(query)

    args = {k: process_kwarg(k, v) for k, v in kwargs.items()}

    rendered_query = template.render(**args)
    response = ddb.execute(rendered_query)
    return DuckResponse(response)


def gather_parquet(input_file: Path, output_file: Path) -> int:
    """
    Given a wildcard path to parquet files, gather them into a single file.
    Returns the row count of the final file
    """
    q = "COPY (select * from {{ input_file }}) TO {{ output_file}} (FORMAT 'parquet')"
    return duck_query(q, input_file=input_file, output_file=output_file).int()
