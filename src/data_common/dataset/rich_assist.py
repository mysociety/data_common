from typing import Any, Callable, Concatenate, Generic, ParamSpec

import pandas as pd
import rich
from rich.console import Group, RenderableType
from rich.panel import Panel
from rich.table import Table

_P = ParamSpec("_P")


class PanelPrint(Generic[_P]):
    """
    Helper for printing list of items in a panel
    """

    def __init__(
        self,
        _panel_class: Callable[Concatenate[Group, _P], Any] = Panel,
        *args: _P.args,
        **kwargs: _P.kwargs,
    ):
        self.items: list[RenderableType] = []
        self.panel_kwargs = kwargs
        self.panel_args = args
        self._panel_class = _panel_class

    def print(self, item: RenderableType) -> None:
        if item is None:
            item = ""
        self.items.append(item)

    def display(self) -> None:
        group = Group(*self.items)
        panel = self._panel_class(group, *self.panel_args, **self.panel_kwargs)
        rich.print(panel)


def df_to_table(
    pandas_dataframe: pd.DataFrame,
    rich_table: Table,
    show_index: bool = True,
    index_name: str | None = None,
) -> Table:
    """Convert a pandas.DataFrame obj into a rich.Table obj.
    Args:
        pandas_dataframe (DataFrame): A Pandas DataFrame to be converted to a rich Table.
        rich_table (Table): A rich Table that should be populated by the DataFrame values.
        show_index (bool): Add a column with a row count to the table. Defaults to True.
        index_name (str, optional): The column name to give to the index column. Defaults to None, showing no value.
    Returns:
        Table: The rich Table instance passed, populated with the DataFrame values."""

    if show_index:
        index_name = str(index_name) if index_name else ""
        rich_table.add_column(index_name)

    for column in pandas_dataframe.columns:
        rich_table.add_column(str(column))

    for index, value_list in enumerate(pandas_dataframe.values.tolist()):
        row = [str(index)] if show_index else []
        row += [str(x) for x in value_list]
        rich_table.add_row(*row)

    return rich_table
