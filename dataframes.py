"""
functions for processing dataframes
"""

import pandas as pd


def markdown_table(obj, *args, format=None, **kwargs):
    """
    changes default to markdown display for tables
    """
    obj = obj.copy()
    if format:
        for c in obj.columns[1:]:
            obj[c] = obj[c].map(lambda n: format.format(n))
    print(obj.to_markdown(index=False, tablefmt="github"))
