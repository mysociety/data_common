import click
from notebook_helper.management.render_processing import DocumentCollection


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
def render(slug="", param=[]):
    doc_collection = dc.collection
    params = {x: y for x, y in param}
    if slug:
        doc = doc_collection.get(slug)
    else:
        doc = doc_collection.first()
    if params:
        print("using custom params")
        print(params)
    doc.render(context=params)


@cli.command()
@click.argument("slug", default="")
def upload(slug=""):
    doc_collection = dc.collection
    if slug:
        doc = doc_collection.get(slug)
    else:
        doc = doc_collection.first()
    doc.upload()
