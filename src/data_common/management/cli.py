import click
from data_common.management.render_processing import DocumentCollection


class DocCollection:
    def __init__(self):
        self.collection = None

    def set_doc_collection(self, collection):
        self.collection = collection


dc = DocCollection()
set_doc_collection = dc.set_doc_collection


@click.group()
def cli():
    pass


@cli.command()
@click.argument("slug", default="")
@click.option("-p", "--param", nargs=2, multiple=True)
@click.option("-g", "--group", nargs=1)
@click.option("--all/--not-all", "render_all", default=False)
@click.option("--publish/--no-publish", default=False)
def render(slug="", param=[], group="", render_all=False, publish=False):
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
def upload(slug="", param=[], render_all=False):
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
