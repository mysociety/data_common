"""
functions to export a notebook in markdown and html
"""

import json
import os
from datetime import datetime
from pathlib import Path

import nbformat
from ipython_genutils.text import indent as normal_indent
from nbconvert import MarkdownExporter, HTMLExporter
from nbconvert.preprocessors import (ClearMetadataPreprocessor,
                                     ClearOutputPreprocessor,
                                     ExecutePreprocessor,
                                     ExtractOutputPreprocessor)
from traitlets.config import Config

notebook_render_dir = "_notebook_resources"


class CustomExtractOutputPreprocessor(ExtractOutputPreprocessor):
    """
    There's a dumb problem somewhere here where resources are being read once
    and not processed, and then it complains when it finds it again
    'fix' this by deleting the first set of references to the images.
    """

    def preprocess_cell(self, cell, resources, cell_index):
        if not hasattr(self, "first_use"):
            resources["outputs"] = {}
            resources["output_files_dir"] = notebook_render_dir
            self.first_use = True
        return super().preprocess_cell(cell, resources, cell_index)


def indent(instr, nspaces=4, ntabs=0, flatten=False):
    """
    do not indent markdown tables when exporting through this filter
    """
    if instr.strip() and instr.strip()[0] == "|":
        return instr
    if "WARN Dropping" in instr:
        return ""
    return normal_indent(instr, nspaces, ntabs, flatten)


class MarkdownRenderer(object):
    self_reference = "render_to_markdown"
    exporter_class = MarkdownExporter
    default_ext = ".md"

    def check_for_self_reference(self, x):
        # scope out the cell that called this function
        # prevent circular call
        for x in x["source"]:
            if "{0}".format(self.__class__.self_reference) in x:
                return True
        return False

    def get_contents(self, input_file):
        with open(input_file) as f:
            nb = json.load(f)

        nb["cells"] = [x for x in nb["cells"]
                       if x["source"] and
                       self.check_for_self_reference(x) is False]
        str_notebook = json.dumps(nb)
        nb = nbformat.reads(str_notebook, as_version=4)
        return nb

    def get_config(self):
        c = Config()
        c.MarkdownExporter.preprocessors = [
            ClearMetadataPreprocessor,
            ClearOutputPreprocessor,
            ExecutePreprocessor,
            CustomExtractOutputPreprocessor
        ]
        c.MarkdownExporter.filters = {"indent": indent}
        c.MarkdownExporter.exclude_input = True
        return c

    def process(self, input_file="readme.ipynb", output_file=None):

        # render clear markdown version of book
        # equiv of `jupyter nbconvert
        # --ClearMetadataPreprocessor.enabled=True
        # --ClearOutput.enabled=True
        # --no-input --execute readme.ipynb --to markdown`

        if os.path.exists(notebook_render_dir) is False:
            os.makedirs(notebook_render_dir)

        if output_file is None:
            output_file = os.path.splitext(
                input_file)[0] + self.__class__.default_ext

        nb = self.get_contents(input_file)

        c = self.get_config()

        markdown = self.__class__.exporter_class(config=c)

        body, resources = markdown.from_notebook_node(nb)

        # write images
        if "outputs" in resources:
            for filename, contents in resources["outputs"].items():
                print("writing: {0}".format(filename))
                with open(filename, "wb") as f:
                    f.write(contents)

        # write markdown
        with open(output_file, "w") as f:
            f.write(body)

        print("Written to {0} at {1}".format(
            output_file, datetime.now(tz=None)))


class HTML_Renderer(MarkdownRenderer):
    self_reference = "render_to_html"
    exporter_class = HTMLExporter
    default_ext = ".html"

    def get_config(self):
        c = Config()
        c.HTMLExporter.preprocessors = [
            ClearMetadataPreprocessor,
            ClearOutputPreprocessor,
            ExecutePreprocessor,
            CustomExtractOutputPreprocessor
        ]
        c.HTMLExporter.exclude_input = False
        return c


render_to_markdown = MarkdownRenderer().process
render_to_html = HTML_Renderer().process
