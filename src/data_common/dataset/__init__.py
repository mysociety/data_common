from __future__ import annotations

import pandas as pd

from .package_models import DataPackageExtras

__all__ = ["DataPackageExtras", "get_dataset_df", "get_dataset_url"]


def get_dataset_url(repo: str, package: str, version: str, file: str) -> str:
    """
    Get url to a dataset from the pages.mysociety.org website.
    """
    return f"https://pages.mysociety.org/{repo}/data/{package}/{version}/{file}"


def get_dataset_df(repo: str, package: str, version: str, file: str) -> pd.DataFrame:
    """
    Get a dataframe from a dataset from the pages.mysociety.org website.
    """
    url = get_dataset_url(repo, package, version, file)
    return pd.read_csv(url)
