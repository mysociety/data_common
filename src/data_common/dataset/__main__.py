import os
import sys
from functools import lru_cache
from pathlib import Path
from sre_constants import ANY
import pandas as pd
import rich
import rich_click as click

from rich.panel import Panel
from rich.table import Table
import json

from .resource_management import DataPackage
from .rich_assist import df_to_table
from .version_management import is_valid_semver
from .settings import get_settings
from .jekyll_management import render_jekyll

from rich.traceback import install

# Turn on rich tracebacks
install(show_locals=False, width=None)


def valid_packages() -> dict[str, DataPackage]:
    settings = get_settings()
    return {
        x.parent.stem: DataPackage(x.parent)
        for x in settings["dataset_dir"].glob("*/datapackage.yaml")
    }


from click.shell_completion import CompletionItem


class SlugType(click.ParamType):
    name = "envvar"

    def shell_complete(self, ctx, param, incomplete):
        return [CompletionItem(x) for x in valid_packages() if x.startswith(incomplete)]


slug_command = click.option(
    "--slug",
    "-s",
    required=False,
    default="",
    show_default=False,
    type=SlugType(),
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


@cli.command("list")
@click.option("--json", "as_json", is_flag=True, help="Output in JSON format")
@click.option(
    "--no-validate", "no_validate", is_flag=True, help="Do not run validation checks"
)
def list_command(as_json: bool = False, no_validate: bool = False):
    """List all datasets"""
    packages = valid_packages()

    df = pd.DataFrame(
        {
            "Package name": [x.slug for x in packages.values()],
            "Config file": [x.datapackage_path for x in packages.values()],
        }
    )

    if no_validate is False:
        df["Resource count"] = [x.resource_count for x in packages.values()]
        df["Current Errors"] = [len(x.validate(quiet=True)) for x in packages.values()]

    table = Table(
        title="Current data package status",
        show_header=True,
        header_style="bold green",
    )

    if as_json is False:
        table = df_to_table(df, table, show_index=False)
        rich.print(table)
    else:
        df["Config file"] = df["Config file"].apply(str)
        rich.print(json.dumps(df.to_dict(orient="records")))


def get_relevant_packages(slug: str, all: bool) -> list[DataPackage]:
    valid = valid_packages()
    current_stem = Path(os.getcwd()).stem
    if len(valid) == 1 or all:
        return list(valid.values())
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
@click.argument("version_or_rule", required=False)
@click.option(
    "--message",
    "-m",
    required=False,
    default="",
    show_default=False,
    help="""Messsage for changelog for version change.
    Can be blank if the rule_type is 'auto'. 
    """,
)
@click.option(
    "--auto-ban",
    "-b",
    required=False,
    default=[],
    multiple=True,
    show_default=False,
    help="""Throw an error if the auto patch rule returns this value (can be used to ban MAJOR updates without erroring on MINOR updates).
    """,
)
@click.option(
    "--dry-run", is_flag=True, help="Run version change without writing to disk"
)
@slug_command
@all_command
def version(
    version_or_rule: str | None = None,
    message: str = "",
    slug: str = "",
    all: bool = False,
    auto_ban: list[str] = [],
    dry_run: bool = False,
):
    """Change the packages version if valid semvar, or bumps automatically if one of MAJOR MINOR PATCH AUTO"""
    if version_or_rule is None:
        version_or_rule = "DISPLAY"
    auto_ban = [x.upper() for x in auto_ban]
    bump_options = ["MAJOR", "MINOR", "PATCH", "AUTO", "INITIAL"]
    package = get_relevant_packages(slug, all)
    if version_or_rule in bump_options and version_or_rule != "AUTO" and message == "":
        raise ValueError("Message required to bump version manually")

    for p in package:
        if version_or_rule == "DISPLAY":
            print(f"{p.slug}: {p.get_current_version()}")
        elif version_or_rule.upper() in bump_options:
            p.bump_version_on_rule(
                version_or_rule.upper(), message, dry_run=dry_run, auto_ban=auto_ban
            )
        elif is_valid_semver(version_or_rule):
            p.bump_version_to(version_or_rule, message)
        else:
            raise ValueError(f"Not a valid semvar or bump rule: {version_or_rule}")


@cli.command(name="update-schema")
@slug_command
@all_command
def update_schema(slug: str = "", all: bool = False):
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
    from cookiecutter.main import cookiecutter

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
        errors = p.validate(quiet=False)
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
    Build a packing using a defined function
    """
    packages = get_relevant_packages(slug, all)
    for p in packages:
        rich.print(f"[blue]Building: {p.slug}[/blue]")
        p.build_from_function()
        p.rebuild_all_resources()


@cli.command()
@slug_command
@all_command
def publish(slug: str = "", all: bool = False):
    """
    Render any missing versions and move them to the jekyll data directory.
    """

    packages = get_relevant_packages(slug, all)
    for p in packages:
        p.rebuild_all_resources()
        p.build_package()
        p.build_missing_previous_versions()
    rich.print("Building Jekyll markdown files")
    render_jekyll()


@cli.command()
def render():
    """
    Build Jekyll pages from the Jekyll's data directory.
    Run as part of build.
    """
    rich.print("Building Jekyll markdown files")
    render_jekyll()


@cli.command()
def auto_complete():
    """
    Returns a command which when run turns on autocomplete
    """
    print(r"eval '$(_DATASET_COMPLETE=bash_source dataset)'")


def run():
    cli()


if __name__ == "__main__":
    run()
