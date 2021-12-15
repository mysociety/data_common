from functools import wraps
from pathlib import Path
from typing import List, Optional

import altair as alt
import pandas as pd
from altair_saver import save as altair_save_chart

from .saver import MSSaver


class Renderer:
    default_renderer = MSSaver


def save_chart(chart, filename, scale_factor=1, **kwargs):
    """
    dumbed down version of altair save function that just assumes
    we're sending extra properties to the embed options
    """
    if isinstance(filename, Path):
        # altair doesn't process paths right
        if filename.parent.exists() is False:
            filename.parent.mkdir()
        filename = str(filename)

    altair_save_chart(
        chart,
        filename,
        scale_factor=scale_factor,
        embed_options=kwargs,
        method=Renderer.default_renderer,
    )


class MSDisplayMixIn:
    """
    mix in that enables a bit more customisation
    of extra display options in the renderer
    """

    ignore_properties = ["_display_options"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._display_options = {}

    def display_options(self, **kwargs):
        """
        arguments passed will be sent to display process
        """
        self._display_options.update(kwargs)
        return self

    def display(self, *args, **kwargs):
        # amended to input the default
        kwargs.update(self._display_options)
        super().display(*args, **kwargs)

    def save(self, *args, **kwargs):
        kwargs.update(self._display_options)
        save_chart(self, *args, **kwargs)

    def to_dict(self, *args, ignore: Optional[List] = None, **kwargs) -> dict:
        if ignore is None:
            ignore = []
        ignore += self.__class__.ignore_properties
        return super().to_dict(*args, ignore=ignore, **kwargs)

    # Layering and stacking
    def __add__(self, other):
        if not isinstance(other, alt.TopLevelMixin):
            raise ValueError("Only Chart objects can be layered.")
        return layer(self, other)

    def __and__(self, other):
        if not isinstance(other, alt.TopLevelMixin):
            raise ValueError("Only Chart objects can be concatenated.")
        return vconcat(self, other)

    def __or__(self, other):
        if not isinstance(other, alt.TopLevelMixin):
            raise ValueError("Only Chart objects can be concatenated.")
        return hconcat(self, other)


class MSDataManagementMixIn:
    """
    Mixin to manage downloading charts
    from the explorer minisites and making it
    slightly easier to edit the data with pandas

    """

    @classmethod
    def from_url(cls, url, n=0):
        from .download import get_chart_from_url

        return get_chart_from_url(url, n)

    def _get_df(self) -> pd.DataFrame:
        return pd.DataFrame(self.datasets[self.data["name"]])

    def update_df(self, df: pd.DataFrame):
        """
        take a new df and update the chart
        """
        self.datasets[self.data["name"]] = df.to_dict("records")
        return self

    @property
    def df(self):
        """
        get the dataset from the chart as a df
        """
        return self._get_df()

    def __setattribute__(self, key, value):
        if key == "df":
            self.update_df(value)
        else:
            super().__setattribute__(key, value)


class Chart(MSDisplayMixIn, MSDataManagementMixIn, alt.Chart):
    pass


class LayerChart(MSDisplayMixIn, MSDataManagementMixIn, alt.LayerChart):
    pass


class HConcatChart(MSDisplayMixIn, MSDataManagementMixIn, alt.HConcatChart):
    pass


class VConcatChart(MSDisplayMixIn, MSDataManagementMixIn, alt.VConcatChart):
    pass


def layer(*charts, **kwargs):
    """layer multiple charts"""
    return LayerChart(layer=charts, **kwargs)


def hconcat(*charts, **kwargs):
    """Concatenate charts horizontally"""
    return HConcatChart(hconcat=charts, **kwargs)


def vconcat(*charts, **kwargs):
    """Concatenate charts horizontally"""
    return VConcatChart(vconcat=charts, **kwargs)


@wraps(Chart.encode)
def ChartEncoding(**kwargs):
    """
    Thin wrapper to specify properties we want to use multiple times
    """
    return kwargs
