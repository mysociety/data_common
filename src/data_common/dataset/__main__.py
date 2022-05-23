import os
import sys
from functools import lru_cache
from pathlib import Path
from sre_constants import ANY
from typing import (
    Any,
    Callable,
    Concatenate,
    Generic,
    List,
    ParamSpec,
    TypedDict,
    TypeVar,
)

import pandas as pd
import rich
import rich_click as click
import toml
from cookiecutter.main import cookiecutter
from rich.panel import Panel
from rich.table import Table

from .resource_management import DataPackage
from .rich_assist import df_to_table
from .settings import get_settings


def valid_packages() -> dict[str, DataPackage]:
    settings = get_settings()
    return {
        x.parent.stem: DataPackage(x.parent)
        for x in settings["dataset_dir"].glob("*/datapackage.yaml")
    }


slug_command = click.option(
    "--slug",
    "-s",
    required=False,
    default="",
    show_default=False,
    help="""Slug of dataset (name of directory).
    Optional if `--all` is set, or if the current directory is a valid dataset.
    """,
)

all_command = click.option("--all", is_flag=True, help="Run for all datasets")
#
@click.group()
def cli():
    """
    Dataset management tool. Validate and publish datasets.
    """
    pass


@cli.command()
def list():
    """List all datasets"""
    packages = valid_packages()

    df = pd.DataFrame(
        {
            "Package name": [x.slug for x in packages.values()],
            "Config file": [x.datapackage_path for x in packages.values()],
            "Resource count": [x.resource_count for x in packages.values()],
            "Current Errors": [len(x.validate()) for x in packages.values()],
        }
    )
    table = Table(
        title="Current data package status",
        show_header=True,
        header_style="bold green",
    )
    table = df_to_table(df, table, show_index=False)

    rich.print(table)


def get_relevant_packages(slug: str, all: bool) -> List[DataPackage]:
    valid = valid_packages()
    current_stem = Path(os.getcwd()).stem
    if all:
        return [x for x in valid.values()]
    elif slug in valid:
        return [valid[slug]]
    elif current_stem in valid:
        return [valid[current_stem]]
    else:
        raise ValueError(
            "No slug specified and current working directory is not a valid package."
        )


@cli.command()
@slug_command
@all_command
def detail(slug: str = "", all: bool = False):
    """View status details for individual resources in a package"""
    package = get_relevant_packages(slug, all)
    for p in package:
        p.print_status()


@cli.command()
@slug_command
@all_command
def refresh(slug: str = "", all: bool = False):
    """Rebuild schema based on any changes to file (retains descs)"""
    packages = get_relevant_packages(slug, all)
    for p in packages:
        rich.print(f"[blue]Building resources for {p.slug}[/blue]")
        p.rebuild_all_resources()


@cli.command()
@slug_command
@all_command
def create(slug: str = "", all: bool = False):
    """Create a new directory for a dataset with a basic template."""

    template_dir = Path(__file__).parent.parent / "resources" / "dataset_template"
    dataset_dir = get_settings()["dataset_dir"]
    final_dir = cookiecutter(str(template_dir), output_dir=str(dataset_dir))
    rich.print(f"[green]New dataset template created in: {final_dir}[/green]")


@cli.command()
@slug_command
@all_command
def validate(slug: str = "", all: bool = False):
    """
    Validate a datapackage against their schema
    """
    error_count = 0
    packages = get_relevant_packages(slug, all)
    for p in packages:
        rich.print(f"[blue]Validating: {p.slug}[/blue]")
        errors = p.validate()
        error_count += len(errors)
        for error, color in errors:
            rich.print(f"[{color}]{error}[/{color}]")

        if not errors:
            rich.print(f"[green]No errors for package.[/green]")
        else:
            rich.print("[red]Run `dataset detail` for more information. [/red]")
        if error_count:
            sys.exit(1)


@cli.command()
@slug_command
@all_command
def build(slug: str = "", all: bool = False):
    """
    Create composite files for publication
    """
    ...
    packages = get_relevant_packages(slug, all)
    for p in packages:
        p.build_package()


def run():
    cli()


if __name__ == "__main__":
    run()
