# data_common

Tools to tidy up jupyter notebook use.
Includes default mysociety theme for altair charts and helper functions to render to markdown readmes.

To use the altair chart with support for our fonts + logo, use `Chart` rather than `alt.Chart`.

In cell code at top include:

```
from data_common.notebook import *

```

and if wanted to automatically render, add this cell code to bottom:

```
# make sure you save before running this
render_to_markdown()
render_to_html()
```

## Updating common dependencies

While working in a repo, if you want to update the common dependencies in the data_common repo.

```
cd src/data_common
poetry add [package] # add package to data_common repo
cd ../..
poetry update # update the lock file for the current repo
```
