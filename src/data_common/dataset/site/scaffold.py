from __future__ import annotations

import keyword
import re
from pathlib import Path

import rich_click as click

from ..settings import find_repo_root

EXTENSION_TEMPLATE = """{% extends "base.html" %}
{% block title %}{{ title }} - {{ site_settings.title }}{% endblock %}
{% block content %}
<h1>{{ title }}</h1>
<p>Your extension content goes here.</p>
{% endblock %}
"""


def render_extension_source(module: str, title: str, route: str) -> str:
    """
    Generate an editable module with a readable, multiline HTML template.
    """
    blueprint_name = module.replace(".", "_")
    return f'''from __future__ import annotations

from pathlib import Path

from flask import Blueprint, render_template_string

from data_common.dataset.site.extensions import SiteExtension
from data_common.dataset.site.models import BuildTarget
from data_common.dataset.site.settings import NavigationItem, SiteSettings

TEMPLATE = """{EXTENSION_TEMPLATE}"""


def create_extension(settings: SiteSettings) -> SiteExtension:
    """
    Create the page, navigation link and static build target.
    """
    blueprint = Blueprint({blueprint_name!r}, __name__)

    @blueprint.get({("/" + route + "/")!r})
    def index() -> str:
        """
        Render the extension with the shared site template.
        """
        return render_template_string(TEMPLATE, title={title!r})

    return SiteExtension(
        blueprint=blueprint,
        targets=[
            BuildTarget(
                settings.site_path({(route + "/")!r}),
                Path({(route + "/index.html")!r}),
            ),
        ],
        navigation=[
            NavigationItem(
                title={title!r},
                url=settings.site_path({(route + "/")!r}),
            ),
        ],
    )
'''


@click.command("create-extension")
@click.option("--module", required=True, help="Import path, e.g. my_project.dashboard.")
@click.option("--title", required=True, help="Page and navigation title.")
@click.option("--route", required=True, help="Site-relative page path, e.g. dashboard.")
@click.option(
    "--repo-root", type=click.Path(path_type=Path, file_okay=False), default=None
)
def create_extension_command(
    module: str,
    title: str,
    route: str,
    repo_root: Path | None,
) -> None:
    """
    Create one editable Python extension file in the repository's src directory.
    """
    parts = module.split(".")
    if not all(part.isidentifier() and not keyword.iskeyword(part) for part in parts):
        raise click.BadParameter(
            "Use a dotted Python module name.", param_hint="--module"
        )
    route = route.strip("/")
    if not re.fullmatch(r"[a-z0-9_-]+(?:/[a-z0-9_-]+)*", route):
        raise click.BadParameter(
            "Use slash-separated lowercase slugs.", param_hint="--route"
        )
    if route.split("/")[0] in {"assets", "data", "datasets", "downloads", "analysis"}:
        raise click.BadParameter(
            "This route is reserved by the dataset site.", param_hint="--route"
        )
    root = (repo_root or find_repo_root()).resolve()
    destination = root / "src" / Path(*parts).with_suffix(".py")
    if not destination.resolve().is_relative_to(root):
        raise click.BadParameter(
            "Module must remain within the repository.", param_hint="--module"
        )
    if destination.exists():
        raise click.ClickException(f"Refusing to overwrite {destination}")
    source = render_extension_source(module, title, route)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(source)
    click.echo(f"Created {destination}")
    click.echo(
        "Add this factory to extensions in [tool.dataset.site] in pyproject.toml:"
    )
    click.echo(f'extensions = ["{module}:create_extension"]')
    click.echo("Then run dataset site serve or dataset site build.")
