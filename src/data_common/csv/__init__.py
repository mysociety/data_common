import requests
import urllib3

import pandas as pd

import ssl

ssl._create_default_https_context = ssl._create_unverified_context
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def get_google_sheet_as_csv(key, outfile, sheet_name=None):
    sheet_url = f"https://docs.google.com/spreadsheets/d/{key}/gviz/tq?tqx=out:csv"
    if sheet_name is not None:
        sheet_url = f"{sheet_url}&sheet={sheet_name}"
    r = requests.get(sheet_url)

    with open(outfile, "wb") as outfile:
        outfile.write(r.content)


def replace_csv_headers(csv_file, new_headers, drop_empty_columns=True, outfile=None):
    if outfile is None:
        outfile = csv_file

    df = pd.read_csv(csv_file)
    if drop_empty_columns:
        df = df.dropna(axis="columns", how="all")

    df.columns = new_headers
    df.to_csv(open(outfile, "w"), index=False, header=True)
