import rich_click as click
from data_common.management.render_processing import DocumentCollection
from typing import Optional, List
from pathlib import Path
from rich import print


class DocCollection:
    def __init__(self):
        self.collection: Optional[DocumentCollection] = None

    def set_doc_collection(self, collection: DocumentCollection):
        self.collection = collection


dc = DocCollection()
set_doc_collection = dc.set_doc_collection

# load all yaml from the config folder
top_level = Path(__file__).parent.parent.parent.parent.parent.parent
notebook_config = top_level / "notebooks" / "_render_config"

doc_collection = DocumentCollection.from_folder(notebook_config)
set_doc_collection(doc_collection)


@click.group()
def cli():
    pass


@cli.command("list")
def listdocs():
    """
    List defined render settings
    """
    for doc in doc_collection.docs.keys():
        print(f"[blue]{doc}[/blue]")


@cli.command()
@click.argument("slug", default="")
@click.option("-p", "--param", nargs=2, multiple=True)
@click.option("-g", "--group", nargs=1)
@click.option("--all/--not-all", "render_all", default=False)
@click.option("--publish/--no-publish", default=False)
def render(
    slug: str = "",
    param: list[str] = [],
    group: str = "",
    render_all: bool = False,
    publish: bool = False,
):
    """
    Render a collection of notebooks to a document
    """
    params = {x: y for x, y in param}

    if dc.collection is None:
        raise ValueError("Doc collection not set")

    if slug:
        docs = [dc.collection.get(slug)]
    elif render_all:
        docs = dc.collection.all()
    elif group:
        docs = dc.collection.get_group(group)
    else:
        docs = [dc.collection.first()]

    if params:
        print("using custom params")
        print(params)

    for doc in docs:
        doc.render(context=params)
        if publish:
            print("starting publication flow")
            doc.upload()


@cli.command()
@click.argument("slug", default="")
@click.option("-p", "--param", nargs=2, multiple=True)
@click.option("--all/--not-all", "render_all", default=False)
def publish(slug="", param=[], render_all=False):
    """
    Publish a previously rendered collection of documents to the chosen export route.
    """
    params = {x: y for x, y in param}

    if dc.collection is None:
        raise ValueError("Doc collection not set")

    if slug:
        docs = [dc.collection.get(slug)]
    elif render_all:
        docs = dc.collection.all()
    else:
        docs = [dc.collection.first()]

    if params:
        print("using custom params")
        print(params)

    for doc in docs:
        doc.upload(params)


def run():
    cli()


if __name__ == "__main__":
    run()
