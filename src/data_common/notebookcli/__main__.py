from __future__ import annotations

import rich_click as click
from rich import print

from .discovery import load_document_collection, selected_documents


@click.group()
def cli() -> None:
    """
    Render and publish configured notebook documents.
    """


@cli.command("list")
def listdocs() -> None:
    """
    List defined render settings.
    """
    collection = load_document_collection()
    for document_name in collection.docs:
        print(f"[blue]{document_name}[/blue]")


@cli.command()
@click.argument("slug", default="")
@click.option("-p", "--param", nargs=2, multiple=True)
@click.option("-g", "--group", nargs=1)
@click.option("--all/--not-all", "render_all", default=False)
@click.option("--publish/--no-publish", default=False)
def render(
    slug: str = "",
    param: tuple[tuple[str, str], ...] = (),
    group: str = "",
    render_all: bool = False,
    publish: bool = False,
) -> None:
    """
    Render a collection of notebooks to a document.
    """
    params = dict(param)
    documents = selected_documents(
        load_document_collection(),
        slug=slug,
        group=group,
        render_all=render_all,
    )

    if params:
        print("using custom params")
        print(params)

    for document in documents:
        document.render(context=params)
        if publish:
            print("starting publication flow")
            document.upload()


@cli.command()
@click.argument("slug", default="")
@click.option("-p", "--param", nargs=2, multiple=True)
@click.option("--all/--not-all", "render_all", default=False)
def publish(
    slug: str = "",
    param: tuple[tuple[str, str], ...] = (),
    render_all: bool = False,
) -> None:
    """
    Publish previously rendered documents to their configured destinations.
    """
    params = dict(param)
    documents = selected_documents(
        load_document_collection(),
        slug=slug,
        render_all=render_all,
    )

    if params:
        print("using custom params")
        print(params)

    for document in documents:
        document.upload(params)


def run() -> None:
    """
    Run the notebook command-line application.
    """
    cli()


if __name__ == "__main__":
    run()
