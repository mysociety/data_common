"""
functions to speed up and pretify notebooks
"""

import builtins as __builtin__
import datetime
import os
import re
import unicodedata
from dataclasses import dataclass
from functools import partial
from pathlib import Path
from typing import Callable, List, Optional, Union

import altair as alt
import numpy as np
import pandas as pd
from IPython.core.display import Markdown as md

from .charting import (
    Chart,
    ChartEncoding,
    ChartTitle,
    altair_sw_theme,
    altair_theme,
    enable_sw_charts,
    reset_renderer,
)
from .pandas.df_extensions import common, space, viz, la
from .helpers.pipe import iter_format
from .management.exporters import render_to_html, render_to_markdown
from .management.settings import settings
from .progress import Progress, track_progress


GovLayers = la.GovLayers

builtin_print = __builtin__.print

pd.options.mode.chained_assignment = None
pd.set_option("display.precision", 2)

image_dir = Path("_images")
render_dir = Path("_render")


def page_break():
    return md(
        """
    ```{=openxml}
<w:p>
  <w:r>
    <w:br w:type="page"/>
  </w:r>
</w:p>
```
"""
    )


while "notebooks" in Path.cwd().parts:
    os.chdir("..")
while (Path.cwd() / "pyproject.toml").exists() is False:
    os.chdir("..")


def notebook_setup():
    reset_renderer()


def Date(x):
    return datetime.datetime.fromisoformat(x).date()


def slugify(value):
    """
    Converts to lowercase, removes non-word characters (alphanumerics and
    underscores) and converts spaces to hyphens. Also strips leading and
    trailing whitespace.
    """
    value = (
        unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    )
    value = re.sub(r"[^\w\s-]", "", value).strip().lower()
    return re.sub(r"[-\s]+", "-", value)


comma_thousands = "{:,}".format
percentage_0dp = "{:,.0%}".format
percentage_1dp = "{:,.1%}".format
percentage_2dp = "{:,.2%}".format
