import inspect
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal, Callable

import duckdb
import jinja2
import pandas as pd
import toml


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
    def __init__(self, duck: "DuckQuery", query: str):
        self._duck = duck
        self._query = query
        self._response = None

    @property
    def response(self) -> duckdb.DuckDBPyConnection:
        if self._response is None:
            self._response = self.get_response()
        return self._response

    def get_response(self) -> duckdb.DuckDBPyConnection:
        return self._duck.ddb.execute(self._query)

    def __iter__(self):
        return iter(self.response.fetchall())

    def to_view(self, name: str) -> "DuckResponse":
        self._duck.add_view(name, self._query)
        return self

    def df(self) -> pd.DataFrame:
        return self.response.df()
    
    def debug_df(self, additional_query: str = "") -> pd.DataFrame:
        """
        Render the result of a query with additional options (like a limit)
        """
        query = f"{self._query} {additional_query}"
        return self._duck.query(query).df()

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

    def run(self) -> None:
        """
        Execute but return nothing
        """
        self.get_response()


class DuckUrl:
    def __init__(self, url: str, file_format: Literal["csv", "parquet"] | None = None):
        # check is https
        if not url.startswith("https://"):
            raise ValueError("URL must start with https://")
        self.url = url
        if file_format:
            self.format = file_format
        else:
            self.format = url.split(".")[-1]

    def __str__(self) -> str:
        return self.url

    # if a divide operattor used, treat like pathlib's Path
    def __truediv__(self, other: str) -> "DuckUrl":
        # check and remove a trailing slash
        if self.url.endswith("/"):
            url = self.url[:-1]
        else:
            url = self.url
        return DuckUrl(f"{url}/{other}")


class DuckQuery:
    def __init__(self):
        self.ddb = duckdb.connect(":memory:")
        self.https: bool = False

    def activate_https(self) -> None:
        if self.https is False:
            self.ddb.execute("install httpfs; load httpfs")

    def register(self, name: str, item: pd.DataFrame | DuckUrl | Path) -> "DuckQuery":

        if isinstance(item, DuckUrl):
            self.activate_https()
            self.ddb.execute(
                f"CREATE OR REPLACE VIEW {name} AS SELECT * FROM '{str(item)}'"
            )
        elif isinstance(item, Path):
            self.ddb.execute(
                f"CREATE OR REPLACE VIEW {name} AS SELECT * FROM '{str(item)}'"
            )
        elif isinstance(item, pd.DataFrame):
            self.ddb.register(name, item)

        return self

    def add_view(self, name: str, query: str) -> "DuckQuery":
        self.ddb.execute(f"CREATE OR REPLACE VIEW {name} AS {query}")
        return self

    def query(
        self, query: str | Path, store_as: str | None = None, **kwargs: Any
    ) -> DuckResponse:
        """
        Execute a query
        """

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
            if isinstance(value, DuckUrl):
                self.activate_https()
                return wrap_str(str(value))
            if isinstance(value, pd.DataFrame):
                self.ddb.register(key, value)
                return key

            return value

        if kwargs:
            env = jinja2.Environment()
            template = env.from_string(query)

            args = {k: process_kwarg(k, v) for k, v in kwargs.items()}

            rendered_query = template.render(**args)
        else:
            rendered_query = query

        if store_as:
            self.ddb.execute(f"CREATE OR REPLACE VIEW {store_as} AS {rendered_query}")
            rendered_query = f"SELECT * FROM {store_as}"
        return DuckResponse(self, rendered_query)
    
    def macro(self, func: Callable[..., str]) -> None:
        # get function name
        name = func.__name__
        # get arguments
        args = func.__code__.co_varnames[:func.__code__.co_argcount]
        # give dummy values for all arguments and get the string contents
        query = func(*[1 for _ in args])
        # register the macro

        macro_query = f"""
        CREATE OR REPLACE MACRO {name}({", ".join(args)}) AS
        {query}
        """
        self.query(macro_query).run()



def duck_query(query: str | Path, **kwargs: Any) -> DuckResponse:
    """
    Helper function to execute a query using duckdb.
    """
    duck = DuckQuery()
    return duck.query(query, **kwargs)


def gather_parquet(input_file: Path, output_file: Path) -> int:
    """
    Given a wildcard path to parquet files, gather them into a single file.
    Returns the row count of the final file
    """
    q = "COPY (select * from {{ input_file }}) TO {{ output_file}} (FORMAT 'parquet')"
    return duck_query(q, input_file=input_file, output_file=output_file).int()
