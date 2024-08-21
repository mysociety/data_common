"""
functions to speed up and pretify notebooks
"""

import datetime
import os
import re
import unicodedata
from pathlib import Path

import pandas as pd
from IPython.core.display import Markdown as md

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


def set_top_level():
    while (Path.cwd() / "pyproject.toml").exists() is False:
        os.chdir("..")


def notebook_setup():
    set_top_level()


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
