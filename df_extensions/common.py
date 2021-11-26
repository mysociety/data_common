import pandas as pd

@pd.api.extensions.register_series_accessor("common")
class CommonAccessor(object):
    """
    extention to pandas dataframe
    """

    def __init__(self, pandas_obj):
        self._obj = pandas_obj

    def update_from_map(self, map: dict) -> pd.Series:
        return self._obj.apply(lambda x: map.get(x, x))


@pd.api.extensions.register_dataframe_accessor("common")
class CommonAccessor(object):
    """
    extention to pandas dataframe
    """

    def __init__(self, pandas_obj):
        self._obj = pandas_obj

    def to_map(self, key_column: str, value_column: str) -> dict:
        return self._obj.set_index(key_column)[value_column].to_dict()

    def row_percentages(self) -> pd.DataFrame:
        df = self._obj
        return df.div(df.sum(axis=1), axis=0)
