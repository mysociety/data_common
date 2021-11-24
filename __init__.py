"""
functions to speed up and pretify notebooks
"""

from .management.exporters import render_to_markdown, render_to_html
from .management.settings import settings
from .charting import (altair_theme, altair_sw_theme, Chart, enable_sw_charts, ChartEncoding)
from .progress import Progress, track_progress
from .helpers.pipe import Pipe, Pipeline, iter_format
from typing import Union, Optional, List, Callable
from functools import partial

import pandas as pd
import numpy as np
import altair as alt
from pathlib import Path
from IPython.display import Markdown as md
import datetime
from dataclasses import dataclass

import builtins as __builtin__
builtin_print = __builtin__.print

pd.options.mode.chained_assignment = None
pd.set_option("display.precision", 2)

image_dir = Path("_images")
render_dir = Path("_render")


def page_break():
    return md("""
    ```{=openxml}
<w:p>
  <w:r>
    <w:br w:type="page"/>
  </w:r>
</w:p>
```
""")


def notebook_setup():
    pass


def Date(x):
    return datetime.datetime.fromisoformat(x).date()


comma_thousands = '{:,}'.format
percentage_1dp = '{:,.1%}'.format
