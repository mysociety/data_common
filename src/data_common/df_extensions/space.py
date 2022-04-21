import math
import random
from functools import reduce, partial
from itertools import combinations, product
from typing import Any, Dict, List, Optional, Union, Tuple, Callable
import copy

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from IPython.display import HTML, display
from ipywidgets import fixed, interact, interact_manual, interactive
from matplotlib.colors import Colormap
from data_common.charting.theme import mysoc_palette_colors
from scipy.spatial.distance import pdist, squareform
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score


from . import viz


def hex_to_rgb(value):
    value = value.lstrip("#")
    lv = len(value)
    t = tuple(int(value[i : i + lv // 3], 16) for i in range(0, lv, lv // 3))
    return t + (0,)


def fnormalize(s):
    return (s - s.mean()) / s.std()


class mySocMap(Colormap):
    def __call__(self, X, alpha=None, bytes=False):
        return mysoc_palette_colors[int(X)]


class Cluster:
    """
    Helper class for finding kgram clusters.
    """

    def __init__(
        self,
        source_df: pd.DataFrame,
        id_col: Optional[str] = None,
        cols: Optional[List[str]] = None,
        label_cols: Optional[List[str]] = None,
        normalize: bool = True,
        transform: List[Callable] = None,
        k: Optional[int] = 2,
    ):
        """
        Initalised with a dataframe, an id column in that dataframe,
        the columns that are the dimensions in question.
        A 'normalize' paramater on if those columns should be
        normalised before use.
        and 'label_cols' which are columns that contain categories
        for items.
        These can be used to help understand clusters.

        """
        self.default_seed = 1221
        self.cluster_results = {}
        self.label_names = {}
        self.label_descs = {}

        self.k = k
        self.normalize = normalize
        self.source_df = source_df
        df = source_df.copy()
        label_df = source_df.copy()

        if id_col:
            df = df.set_index(id_col)
            label_df = label_df.set_index(id_col)
        else:
            id_col = df.index.name

        if label_cols:
            df = df.drop(columns=label_cols)
        else:
            label_cols = []

        if cols:
            df = df[cols]
        else:

            def t(x):
                return x != id_col and x not in label_cols

            cols = list(filter(t, source_df.columns))

        if normalize:
            df = df.apply(fnormalize, axis=0)
        if transform:
            for k, v in transform.items():
                df[k] = v(df[k])

        self.df = df
        self.cols = cols
        self.id_col = id_col
        self.label_cols = label_cols

        not_allowed = cols + label_cols
        label_df = label_df.drop(
            columns=[x for x in label_df.columns if x not in not_allowed]
        )
        for c in cols:
            try:
                labels = ["Low", "Medium", "High"]
                q = pd.qcut(label_df[c], 3, labels=labels, duplicates="drop")
                label_df[c] = q
            except ValueError:
                pass

        label_df["Total"] = "Total"

        self.label_df = label_df

    def set_k(self, k: int) -> "Cluster":

        new = copy.deepcopy(self)

        new.k = k
        return new

    def get_label_name(self, n, include_short=True) -> str:

        short_label = n + 1
        name = self.label_names.get(self.k, {}).get(n, short_label)
        if include_short:
            if name != short_label:
                name = f"{short_label}: {name}"
        return name

    def get_label_desc(self, n) -> str:
        short_label = n + 1
        name = self.label_descs.get(self.k, {}).get(n, short_label)
        return name

    def get_label_options(self) -> list:

        return [self.get_label_name(x) for x in range(0, self.k)]

    def get_cluster_label_ids(self) -> pd.Series:
        labels = pd.Series(self.get_clusters(self.k).labels_) + 1
        return labels

    def get_cluster_labels(self, include_short=True) -> np.array:

        labels = pd.Series(self.get_clusters(self.k).labels_)

        def f(x):
            return self.get_label_name(n=x, include_short=include_short)

        labels = labels.apply(f)
        return np.array(labels)

    label_array = get_cluster_labels

    def get_cluster_descs(self) -> np.array:

        labels = pd.Series(self.get_clusters(self.k).labels_)
        labels = labels.apply(lambda x: self.get_label_desc(n=x))
        return np.array(labels)

    def add_labels(self, labels: Dict[int, Union[str, Tuple[str, str]]]):
        """
        Assign labels to clusters
        Expects a dictionary of cluster number to label
        Label can be a tuple of a label and a longer description
        """
        new = copy.deepcopy(self)

        for n, label in labels.items():
            desc = ""
            if isinstance(label, tuple):
                desc = label[1]
                label = label[0]
            new.assign_name(n, label, desc)

        return new

    def assign_name(self, n: int, name: str, desc: Optional[str] = ""):
        k = self.k
        if k not in self.label_names:
            self.label_names[k] = {}
            self.label_descs[k] = {}
        self.label_names[k][n - 1] = name
        self.label_descs[k][n - 1] = desc

    def plot(
        self,
        limit_columns: Optional[List[str]] = None,
        only_one: Optional[Any] = None,
        show_legend: bool = True,
    ):
        """
        Plot either all possible x, y graphs for k clusters
        or just the subset with the named x_var and y_var.
        """
        k = self.k
        df = self.df

        num_rows = 3

        vars = self.cols
        if limit_columns:
            vars = [x for x in vars if x in limit_columns]
        combos = list(combinations(vars, 2))
        rows = math.ceil(len(combos) / num_rows)

        plt.rcParams["figure.figsize"] = (15, 5 * rows)

        df["labels"] = self.get_cluster_labels()

        if only_one:
            df["labels"] = df["labels"] == only_one
            df["labels"] = df["labels"].map({True: only_one, False: "Other clusters"})
        chart_no = 0

        rgb_values = sns.color_palette("Set2", len(df["labels"].unique()))
        color_map = dict(zip(df["labels"].unique(), rgb_values))
        fig = plt.figure()

        for x_var, y_var in combos:
            chart_no += 1
            ax = fig.add_subplot(rows, num_rows, chart_no)
            for c, d in df.groupby("labels"):
                scatter = ax.scatter(d[x_var], d[y_var], color=color_map[c], label=c)

            ax.set_xlabel(self._axis_label(x_var))
            ax.set_ylabel(self._axis_label(y_var))
            if show_legend:
                ax.legend()

        plt.show()

    def plot_tool(self):
        def func(cluster, show_legend, **kwargs):
            if cluster == "All":
                cluster = None
            limit_columns = [x for x, y in kwargs.items() if y is True]
            self.plot(
                only_one=cluster, show_legend=show_legend, limit_columns=limit_columns
            )

        cluster_options = ["All"] + self.get_label_options()

        analysis_options = {
            x: True if n < 2 else False for n, x in enumerate(self.cols)
        }

        tool = interactive(
            func,
            cluster=cluster_options,
            **analysis_options,
            show_legend=False,
        )
        display(tool)

    def _get_clusters(self, k: int):
        """
        fetch k means results for this cluster
        """
        km = KMeans(n_clusters=k, random_state=self.default_seed)
        return km.fit(self.df)

    def get_clusters(self, k: int):
        """
        fetch from cache if already run for this value of k
        """
        if k not in self.cluster_results:
            self.cluster_results[k] = self._get_clusters(k)
        return self.cluster_results[k]

    def find_k(self, start: int = 15, stop: Optional[int] = None, step: int = 1):
        """
        Graph the elbow and Silhouette method for finding the optimal k.
        High silhouette value good.
        Parameters are the search space.
        """
        if start and not stop:
            stop = start
            start = 2

        def s_score(kmeans):
            return silhouette_score(self.df, kmeans.labels_, metric="euclidean")

        df = pd.DataFrame({"n": range(start, stop, step)})
        df["k_means"] = df["n"].apply(self.get_clusters)
        df["sum_squares"] = df["k_means"].apply(lambda x: x.inertia_)
        df["silhouette"] = df["k_means"].apply(s_score)

        plt.rcParams["figure.figsize"] = (10, 5)
        plt.subplot(1, 2, 1)
        plt.plot(df["n"], df["sum_squares"], "bx-")
        plt.xlabel("k")
        plt.ylabel("Sum of squared distances")
        plt.title("Elbow Method For Optimal k")

        plt.subplot(1, 2, 2)
        plt.plot(df["n"], df["silhouette"], "bx-")
        plt.xlabel("k")
        plt.ylabel("Silhouette score")
        plt.title("Silhouette Method For Optimal k")
        plt.show()

    def stats(self, label_lookup: Optional[dict] = None, all_members: bool = False):
        """
        Simple description of sample size
        """
        k = self.k
        if label_lookup is None:
            label_lookup = {}

        df = pd.DataFrame({"labels": self.get_cluster_labels()})
        df.index = self.df.index
        df = df.reset_index()

        pt = df.pivot_table(self.id_col, index="labels", aggfunc="count")
        pt = pt.rename(columns={self.id_col: "count"})
        pt["%"] = (pt["count"] / len(df)).round(3) * 100

        def all_items(s: List[str]) -> List[str]:
            return [label_lookup.get(x, x) for x in s]

        def random_set(s: List[str]) -> List[str]:
            labels = all_items(s)
            random.shuffle(labels)
            return labels[:5]

        if all_members:
            d = df.groupby("labels").agg(all_items)
        else:
            d = df.groupby("labels").agg(random_set)

        pt = pt.join(d)
        if all_members:
            pt = pt.rename(columns={self.id_col: "all members"})
        else:
            pt = pt.rename(columns={self.id_col: "random members"})
        return pt

    def raincloud(
        self,
        column: str,
        one_value: Optional[str] = None,
        groups: Optional[str] = "Cluster",
        use_source: bool = True,
    ):
        """
        raincloud plot of a variable, grouped by different clusters

        """
        k = self.k
        if use_source:
            df = self.source_df.copy()
        else:
            df = self.df
        df["Cluster"] = self.get_cluster_labels()
        df.viz.raincloud(
            values=column,
            groups=groups,
            one_value=one_value,
            title=f"Raincloud plot for {column} variable.",
        )

    def reverse_raincloud(self, cluster_label: str):
        """
        Raincloud plot for a single cluster showing the
        distribution of different variables
        """
        df = self.df.copy()
        df["Cluster"] = self.get_cluster_labels()
        df = df.melt("Cluster")[lambda df: ~(df["variable"] == " ")]
        df["value"] = df["value"].astype(float)
        df = df[lambda df: (df["Cluster"] == cluster_label)]

        df.viz.raincloud(
            values="value",
            groups="variable",
            title=f"Raincloud plot for Cluster: {cluster_label}",
        )

    def reverse_raincloud_tool(self):
        """
        Raincloud tool to examine clusters showing the
        distribution of different variables
        """
        tool = interactive(
            self.reverse_raincloud, cluster_label=self.get_label_options()
        )
        display(tool)

    def raincloud_tool(self, reverse: bool = False):
        """
        Raincloud tool to examine variables showing the
        distribution of different clusters
        The reverse option flips this.
        """
        if reverse:
            return self.reverse_raincloud_tool()

        def func(variable, comparison, use_source_values):
            groups = "Cluster"
            if comparison == "all":
                comparison = None
            if comparison == "none":
                groups = None
                comparison = None
            self.raincloud(
                variable,
                one_value=comparison,
                groups=groups,
                use_source=use_source_values,
            )

        comparison_options = ["all", "none"] + self.get_label_options()
        tool = interactive(
            func,
            variable=self.cols,
            use_source_values=True,
            comparison=comparison_options,
        )

        display(tool)

    def label_tool(self):
        """
        tool to review how labels assigned for each cluster

        """
        k = self.k

        def func(cluster, sort, include_data_labels):
            if sort == "Index":
                sort = None
            df = self.label_review(
                label=cluster, sort=sort, include_data=include_data_labels
            )
            display(df)
            return df

        sort_options = ["Index", "% of cluster", "% of label"]
        tool = interactive(
            func,
            cluster=self.get_label_options(),
            sort=sort_options,
            include_data_labels=True,
        )
        display(tool)

    def label_review(
        self,
        label: Optional[int] = 1,
        sort: Optional[str] = None,
        include_data: bool = True,
    ):
        """
        Review labeled data for a cluster
        """

        k = self.k

        def to_count_pivot(df):
            mdf = df.drop(columns=["label"]).melt()
            mdf["Count"] = mdf["variable"] + mdf["value"]
            return mdf.pivot_table(
                "Count", index=["variable", "value"], aggfunc="count"
            )

        df = self.label_df
        if include_data is False:
            df = df[[x for x in df.columns if x not in self.cols]]
        df["label"] = self.get_cluster_labels()
        opt = to_count_pivot(df).rename(columns={"Count": "overall_count"})
        df = df.loc[df["label"] == label]
        pt = to_count_pivot(df).join(opt)
        pt = pt.rename(columns={"Count": "cluster_count"})
        pt["% of cluster"] = (pt["cluster_count"] / len(df)).round(3) * 100
        pt["% of label"] = (pt["cluster_count"] / pt["overall_count"]).round(3) * 100
        if sort:
            pt = pt.sort_values(sort, ascending=False)
        return pt

    def _axis_label(self, label_txt: str) -> str:
        """
        Extend axis label with extra notes
        """
        txt = label_txt
        if self.normalize:
            txt = txt + " (normalized)"
        return txt

    def df_with_labels(self) -> pd.DataFrame:
        """
        return the original df but with a label column attached
        """
        k = self.k
        df = self.source_df.copy()
        df["label"] = self.get_cluster_labels(include_short=False)
        df["label_id"] = self.get_cluster_label_ids()
        df["label_desc"] = self.get_cluster_descs()
        return df

    def plot3d(
        self,
        x_var: Optional[str] = None,
        y_var: Optional[str] = None,
        z_var: Optional[str] = None,
    ):
        k = self.k
        """
        Plot either all possible x, y, z graphs for k clusters
        or just the subset with the named x_var and y_var.
        """
        df = self.df

        labels = self.get_cluster_labels()
        combos = list(combinations(df.columns, 3))
        if x_var:
            combos = [x for x in combos if x[0] == x_var]
        if y_var:
            combos = [x for x in combos if x[1] == y_var]
        if z_var:
            combos = [x for x in combos if x[1] == y_var]
        rows = math.ceil(len(combos) / 2)

        plt.rcParams["figure.figsize"] = (20, 10 * rows)

        chart_no = 0
        fig = plt.figure()
        for x_var, y_var, z_var in combos:
            chart_no += 1
            ax = fig.add_subplot(rows, 2, chart_no, projection="3d")
            ax.scatter(df[x_var], df[y_var], df[z_var], c=labels)
            ax.set_xlabel(self._axis_label(x_var))
            ax.set_ylabel(self._axis_label(y_var))
            ax.set_zlabel(self._axis_label(z_var))
            plt.title(f"Data with {k} clusters")

        plt.show()


def join_distance(df_label_dict: Dict[str, pd.DataFrame]) -> pd.DataFrame:
    """
    Expects the results of df.space.self_distance to be put into
    the dataframes in the input
    Will merge multiple kinds of distance into a common dataframe
    the str in the dictionary it expects is the label for the column
    """

    def prepare(df, label):

        return (
            df.set_index(list(df.columns[:2]))
            .rename(columns={"distance": label})
            .drop(columns=["match", "position"], errors="ignore")
        )

    to_join = [prepare(df, label) for label, df in df_label_dict.items()]
    df = reduce(lambda x, y: x.join(y), to_join)
    df = df.reset_index()
    return df


@pd.api.extensions.register_dataframe_accessor("space")
class SpacePDAccessor(object):
    """
    extention to pandas dataframe
    """

    def __init__(self, pandas_obj):
        self._obj = pandas_obj

    def cluster(
        self,
        id_col: Optional[str] = None,
        cols: Optional[List[str]] = None,
        label_cols: Optional[List[str]] = None,
        normalize: bool = True,
        transform: List[Callable] = None,
        k: Optional[int] = None,
    ) -> Cluster:
        """
        returns a Cluster helper object for this dataframe
        """
        return Cluster(
            self._obj,
            id_col=id_col,
            cols=cols,
            label_cols=label_cols,
            normalize=normalize,
            transform=transform,
            k=k,
        )

    def self_distance(
        self,
        id_col: Optional[str] = None,
        cols: Optional[List] = None,
        normalize: bool = False,
        transform: List[callable] = None,
    ):
        """
        Calculate the distance between all objects in a dataframe
        in an n-dimensional space.
        get back a dataframe with two labelled columns as well as the
        distance.
        id_col : unique column containing an ID or similar
        cols: all columns to be used in the calculation of distance
        normalize: should these columns be normalised before calculating
        distance
        transform: additonal functions to apply to columns after normalizating

        """
        source_df = self._obj

        if id_col == None:
            id_col = source_df.index.name
            source_df = source_df.reset_index()

        if id_col not in source_df.columns:
            source_df = source_df.reset_index()

        if cols is None:
            cols = [x for x in source_df.columns if x != id_col]

        a_col = id_col + "_A"
        b_col = id_col + "_B"
        _ = list(product(source_df[id_col], source_df[id_col]))

        df = pd.DataFrame(_, columns=[a_col, b_col])

        grid = source_df[cols]
        # normalise columns
        if normalize:
            grid = grid.apply(fnormalize, axis=0)

        if transform:
            for k, v in transform.items():
                grid[k] = v(grid[k])

        distance = pdist(grid.to_numpy())
        # back into square grid, flatten to 1d
        df["distance"] = squareform(distance).flatten()
        df = df.loc[~(df[a_col] == df[b_col])]
        return df

    def join_distance(
        self,
        other: Union[Dict[str, pd.DataFrame], pd.DataFrame],
        our_label: Optional[str] = "A",
        their_label: Optional[str] = "B",
    ):
        """
        Either merges self and other
        (both of whichs hould be the result of
        space.self_distance)
        or a dictionary of dataframes and labels
        not including the current dataframe.
        """

        if not isinstance(other, dict):
            df_label_dict = {our_label: self._obj, their_label: other}
        else:
            df_label_dict = other

        return join_distance(df_label_dict)

    def match_distance(self):
        """
        add a match percentage column where the tenth most distance is a 0% match
        and 0 distance is an 100% match.
        """
        df = self._obj

        def standardise_distance(df):
            df = df.copy()
            # use tenth from last because the last point might be an extreme outlier (in this case london)
            tenth_from_last_score = df["distance"].sort_values().tail(10).iloc[0]
            df["match"] = 1 - (df["distance"] / tenth_from_last_score)
            df["match"] = df["match"].round(3) * 100
            df["match"] = df["match"].apply(lambda x: x if x > 0 else 0)
            df = df.sort_values("match", ascending=False)
            return df

        return (
            df.groupby(df.columns[0], as_index=False)
            .apply(standardise_distance)
            .reset_index(drop=True)
        )

    def local_rankings(self):
        """
        add a position column that indicates the relative similarity based on distance
        """
        df = self._obj

        def get_position(df):
            df["position"] = df["distance"].rank(method="first")
            return df

        return (
            df.groupby(df.columns[0], as_index=False)
            .apply(get_position)
            .reset_index(drop=True)
        )


@pd.api.extensions.register_dataframe_accessor("joint_space")
class JointSpacePDAccessor(object):
    """
    handles dataframes that have joined several distance calculations

    """

    def __init__(self, pandas_obj):
        self._obj = pandas_obj

    def composite_distance(self, normalize: bool = False):
        """
        Given all distances in joint space,
        calculate a composite.
        Set normalize to true to scale all distances between 0 and 1
        Shouldn't be needed where a product of previous rounds of normalization
        A scale factor of 2 for a column reduces distances by half
        """
        df = self._obj.copy()

        def normalize_series(s: pd.Series):
            return s / s.max()

        cols = df.columns[2:]
        cols = [df[x] for x in cols]

        if normalize:
            cols = [normalize_series(x) for x in cols]

        squared_cols = [x ** 2 for x in cols]
        res = reduce(pd.Series.add, squared_cols)  # add squared cols
        res = res.apply(np.sqrt)  # get square root

        ndf = df[df.columns[:2]]
        ndf["distance"] = res
        return ndf

    def same_nearest_k(self, k: int = 5):
        """
        Expects the dataframe returned by `join_distance`.
        Groups by column 1, Expects first two columns to be id columns.
        Beyond that, will see if all columns (representing distances)
        have the same items
        in their lowest 'k' matches.
        Returns a column that can be averaged to get the overlap between
        two metrics.
        """
        df = self._obj

        def top_k(df, k=5):
            df = df.set_index(list(df.columns[:2])).rank()
            df = df <= k
            same_rank = df.sum(axis=1).reset_index(drop=True) == len(list(df.columns))
            data = [[same_rank.sum() / k]]
            d = pd.DataFrame(data, columns=[f"same_top_{k}"])
            return d.iloc[0]

        return df.groupby(df.columns[0]).apply(top_k, k=k).reset_index()

    def agreement(self, ks: List[int] = [1, 2, 3, 5, 10, 25]):
        """
        Given the result of 'join_distance' explore how similar
        items fall in 'top_k' for a range of values of k.
        """

        df = self._obj

        def get_average(k):
            return df.joint_space.same_nearest_k(k=k).mean().round(2)[0]

        r = pd.DataFrame({"top_k": ks})
        r["agreement"] = r["top_k"].apply(get_average)
        return r

    def plot(self, sample=None, kind="scatter", title="", **kwargs):
        """
        simple plot of distance
        """
        df = self._obj
        if sample:
            df = df.sample(sample)
        plt.rcParams["figure.figsize"] = (10, 5)
        df.plot(x=df.columns[2], y=df.columns[3], kind=kind, title=title, **kwargs)
