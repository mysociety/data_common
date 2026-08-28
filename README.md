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

Dependencies for the shared package live in `pyproject.toml`. The base package is deliberately small; install the feature extras needed by the repository.

```bash
# The normal data-publication environment
uv sync --extra dataset

# Work on every data_common feature
uv sync --all-extras
```

The available extras are:

- `dataset` — the standard dataset build, validation and publication workflow
- `notebook` — lightweight notebook helpers
- `render` — notebook-to-Markdown/HTML/DOCX rendering
- `google` — Google Drive and Docs publication
- `charts` — Altair chart creation and rendering
- `analysis` — plotting, clustering and scientific-analysis helpers
- `geo` — GeoPandas and parquet helpers
- `db` — standalone DuckDB helpers
- `validation` — Pydantic URL helpers

The `dev` dependency group supplies Ruff, Pyright and type stubs. uv installs it by default.
