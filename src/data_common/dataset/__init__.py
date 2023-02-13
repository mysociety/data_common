import pandas as pd


def get_dataset_url(repo: str, package: str, version: str, file: str):
    """
    Get url to a dataset from the pages.mysociety.org website.
    """
    return f"https://pages.mysociety.org/{repo}/data/{package}/{version}/{file}"


def get_dataset_df(repo: str, package: str, version: str, file: str):
    """
    Get a dataframe from a dataset from the pages.mysociety.org website.
    """
    url = get_dataset_url(repo, package, version, file)
    return pd.read_csv(url)
