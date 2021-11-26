from typing import List, Optional, Dict
import pandas as pd

import ptitprince as pt
import seaborn as sns
import matplotlib.collections as clt
import matplotlib.pyplot as plt


sns.set(style="whitegrid", font_scale=1, font="Source Sans Pro")


@pd.api.extensions.register_series_accessor("viz")
class VIZSeriesAccessor:

    def __init__(self, pandas_obj):
        self._obj = pandas_obj

    def raincloud(self,
                  groups: Optional[pd.Series] = None,
                  ort: Optional[str] = "h",
                  pal: Optional[str] = "Set2",
                  sigma: Optional[float] = .2,
                  title: str = "",
                  all_data_label: str = "All data",
                  x_label: Optional[str] = None,
                  y_label: Optional[str] = None,
                  ):
        """
        show a raincloud plot of the values of a series
        Optional split by a second series (group)
        with labels.
        """

        s = self._obj
        df = pd.DataFrame(s)

        if groups is not None:
            df[groups.name] = groups
            x_col = groups.name
        else:
            df[" "] = all_data_label
            x_col = " "

        f, ax = plt.subplots(figsize=(14, 2*df[x_col].nunique()))
        pt.RainCloud(x=df[x_col], y=df[s.name], palette=pal, bw=sigma,
                     width_viol=.6, ax=ax, orient=ort, move=.3)
        if title:
            plt.title(title, loc="center", fontdict={"fontsize": 30})
        if x_label is not None:
            plt.xlabel(x_label, fontdict={"fontsize": 12})
        if y_label is not None:
            plt.ylabel(y_label, fontdict={"fontsize": 12}, rotation=0)
        plt.show()


@pd.api.extensions.register_dataframe_accessor("viz")
class VIZDFAccessor:

    def __init__(self, pandas_obj):
        self._obj = pandas_obj

    def raincloud(self,
                  values: str,
                  groups: Optional[str] = None,
                  one_value: Optional[str] = None,
                  limit: Optional[List[str]] = None,
                  ort: Optional[str] = "h",
                  pal: Optional[str] = "Set2",
                  sigma: Optional[float] = .2,
                  title: Optional[str] = "",
                  all_data_label: str = "All data",
                  x_label: Optional[str] = None,
                  y_label: Optional[str] = None,):
        """
        helper function for visualising one column against
        another with raincloud plots.
        """

        df = self._obj

        if limit:
            df = df.loc[df[groups].isin(limit)]

        if groups is None:
            df[" "] = all_data_label
            groups = " "

        if one_value:
            df[groups] = (df[groups] == one_value).map(
                {False: "Other clusters", True: one_value})

        f, ax = plt.subplots(figsize=(14, 2*df[groups].nunique()))
        pt.RainCloud(x=df[groups], y=df[values], palette=pal, bw=sigma,
                     width_viol=.6, ax=ax, orient=ort, move=.3)
        if title:
            plt.title(title, loc="center", fontdict={"fontsize": 30})
        if x_label is not None:
            plt.xlabel(x_label, fontdict={"fontsize": 12})
        if y_label is not None:
            plt.ylabel(y_label, fontdict={"fontsize": 12}, rotation=0)
        plt.show()
