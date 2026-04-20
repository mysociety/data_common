from os.path import join
import pandas as pd

from ..dataset import get_dataset_df

def fix_council_name(council: str) -> str:
    return (
        council.replace("council", "")
        .replace(" - unitary", "")
        .replace("(unitary)", "")
        .strip()
    )

def add_local_authority_code(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add the local-authority-code to the dataframe
    """

    name_to_code = get_dataset_df(
        repo="uk_local_authority_names_and_codes",
        package="uk_la_past_current",
        version="1",
        file="lookup_name_to_registry.csv",
    )
    df["council_lower"] = df["council"].str.lower().apply(fix_council_name)
    name_to_code["council_lower"] = (
        name_to_code["la-name"].str.lower().apply(fix_council_name)
    )
    df = df.merge(name_to_code, on="council_lower", how="left")

    # local-authority-code is in last position, move it to the start of the dataframe
    cols = list(df.columns)
    cols.insert(0, cols.pop(-1))
    df = df[cols]
    df = df.drop(columns=["council_lower", "la-name"])
    return df

def add_region_and_county(df: pd.DataFrame) -> pd.DataFrame:
    name_to_code = get_dataset_df(
        repo="uk_local_authority_names_and_codes",
        package="uk_la_past_current",
        version="1",
        file="uk_local_authorities_current.csv",
    )

    rows = len(df["council"])
    df["region"] = pd.Series([None] * rows, index=df.index)
    df["county"] = pd.Series([None] * rows, index=df.index)

    for index, row in df.iterrows():
        authority_code = row["local-authority-code"]
        if not pd.isnull(authority_code):
            authority_match = name_to_code[
                name_to_code["local-authority-code"] == authority_code
            ]
            df.at[index, "region"] = authority_match["region"].values[0]
            df.at[index, "county"] = authority_match["county-la"].values[0]

    return df


def add_gss_codes(df: pd.DataFrame) -> pd.DataFrame:
    name_to_code = get_dataset_df(
        repo="uk_local_authority_names_and_codes",
        package="uk_la_past_current",
        version="1",
        file="uk_local_authorities_current.csv",
    )

    rows = len(df["council"])
    df["gss_code"] = pd.Series([None] * rows, index=df.index)

    for index, row in df.iterrows():
        authority_code = row["local-authority-code"]
        if not pd.isnull(authority_code):
            authority_match = name_to_code[
                name_to_code["local-authority-code"] == authority_code
            ]
            df.at[index, "gss_code"] = authority_match["gss-code"].values[0]

    return df


def add_extra_authority_info(df: pd.DataFrame) -> pd.DataFrame:
    name_to_code = get_dataset_df(
        repo="uk_local_authority_names_and_codes",
        package="uk_la_past_current",
        version="1",
        file="uk_local_authorities_current.csv",
    )

    extra_df = name_to_code[
        [
            "local-authority-code",
            "local-authority-type",
            "wdtk-id",
            "mapit-area-code",
            "nation",
            "gss-code",
        ]
    ]

    # the info sheet may contain updated version of columns previously
    # loaded to sheet, need to drop them before the merge
    # ignore errors in case columns are not present
    columns_to_drop = [x for x in extra_df.columns if x != "local-authority-code"]
    df = df.drop(columns=columns_to_drop, errors="ignore")

    # merge two dataframes using the authority_code as the common reference
    extra_df = extra_df.merge(df, on="local-authority-code", how="left")

    is_non_english = extra_df["nation"].isin(["Wales", "Scotland", "Northern Ireland"])
    extra_df.loc[is_non_english, "local-authority-type"] = "UA"

    return extra_df
