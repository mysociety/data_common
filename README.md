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

## Dataset site extensions

Create a project-local page with shared templates and static publication:

```bash
dataset create-extension --module my_project.example --title "Example" --route example
```

The command writes `src/my_project/example.py` (without overwriting existing
files) and prints the configuration to add to `pyproject.toml`:

```toml
[tool.dataset.site]
extensions = ["my_project.example:create_extension"]
```

Use `--repo-root PATH` to scaffold in another repository. The module must be
importable in the site's environment. Add to an existing extensions list instead
of replacing it.

An extension factory accepts `SiteSettings` and returns
`data_common.dataset.site.extensions.SiteExtension`:

- `blueprint`: a Flask blueprint, registered under the site's `base_url` followed
  by its own `url_prefix`, if set. Namespace template names, e.g.
  `example/index.html`, and extend `base.html` for shared
  layout. `site_settings`, `site_path` and shared navigation are available.
- `targets`: a list of `BuildTarget(url, destination, mimetype="text/html")`.
  URLs include the base path; destinations are relative paths such as
  `example/index.html`. Set `mimetype=None` to skip response MIME validation.
  Declare every static state explicitly. Use path segments rather than query
  parameters for filters that must work on static hosting.
- `navigation`: optional `NavigationItem` entries shown in the header and the
  homepage Tools list; construct their URLs with
  `settings.site_path`.

Routes with the same path pattern and overlapping HTTP methods are rejected.
Parameter names do not distinguish patterns (`/<id>` and `/<name>` conflict).
Separate GET and POST handlers are allowed; OPTIONS is ignored for this check.
Different converters and static versus variable routes use Flask's normal
precedence; the check does not detect every possible overlapping pattern.

Blueprint static folders are automatically included in builds. Set a namespaced
`static_url_path`, e.g. `/example/assets`, and link with
`url_for("blueprint_name.static", filename="page.css")`. Core `assets/`, `data/`
and analysis `notebook_resources/` output directories are reserved, along with
the generated `.nojekyll` file. The builder rejects duplicate targets, unsafe
paths and file/directory collisions before cleaning existing output. Declared
pages and discovered assets appear in `dataset site routes` and pass through the
same response and link checks as core pages. Asset URLs remain URL-encoded while
output filenames and link checks use decoded paths. Discovered assets do not
modify the factory's target list.

No extensions are loaded unless explicitly configured. Factories run once per
app; they should read prepared local data rather than fetch remote data or write
files.
