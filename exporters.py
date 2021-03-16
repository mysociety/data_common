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
                                     ExtractOutputPreprocessor,
                                     Preprocessor)
from traitlets.config import Config

notebook_render_dir = "_notebook_resources"


class RemoveOnContent(Preprocessor):
    """
    remove on some content flags
    """

    def preprocess(self, nb, resources):

        # Filter out cells that meet the conditions
        nb.cells = [self.preprocess_cell(cell, resources, index)[0]
                    for index, cell in enumerate(nb.cells)]

        return nb, resources

    def preprocess_cell(self, cell, resources, cell_index):
        """
        Apply a transformation on each cell. See base.py for details.
        """

        if cell["source"]:
            if "#HIDE" == cell["source"][:5]:
                cell.transient = {
                    'remove_source': True
                }

        return cell, resources


class CustomExtractOutputPreprocessor(ExtractOutputPreprocessor):
    """
    There's a dumb problem somewhere here where resources are being read once
    and not processed, and then it complains when it finds it again
    'fix' this by deleting the first set of references to the images.
    """

    def preprocess_cell(self, cell, resources, cell_index):
        if not hasattr(self, "first_use"):
            resources["outputs"] = {}
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


def check_string_in_source(instr, item):
    for x in item["source"]:
        if instr in x:
            return True
    return False


class MarkdownRenderer(object):
    self_reference = "render_to_markdown"
    exporter_class = MarkdownExporter
    default_ext = ".md"
    include_input = False

    def __init__(self, include_input=None):
        if include_input is None:
            include_input = self.__class__.include_input
        self.include_input = include_input

    def check_for_self_reference(self, cell):
        # scope out the cell that called this function
        # prevent circular call
        contains_str = check_string_in_source(
            self.__class__.self_reference, cell)
        is_code = cell["cell_type"] == "code"
        return contains_str and is_code

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
            CustomExtractOutputPreprocessor,
            RemoveOnContent
        ]
        c.MarkdownExporter.filters = {"indent": indent}
        c.MarkdownExporter.exclude_input = not self.include_input
        return c

    def process(self, input_file="readme.ipynb", output_file=None):

        # render clear markdown version of book
        # equiv of `jupyter nbconvert
        # --ClearMetadataPreprocessor.enabled=True
        # --ClearOutput.enabled=True
        # --no-input --execute readme.ipynb --to markdown`

        if os.path.exists(notebook_render_dir) is False:
            os.makedirs(notebook_render_dir)

        base = os.path.basename(input_file)
        base_root = os.path.splitext(base)[0]

        if output_file is None:
            output_file = os.path.splitext(
                input_file)[0] + self.__class__.default_ext

        nb = self.get_contents(input_file)

        c = self.get_config()

        exporter = self.__class__.exporter_class(config=c)

        resources = {"output_files_dir": notebook_render_dir,
                     "unique_key": base_root}

        body, resources = exporter.from_notebook_node(nb, resources)

        # write images
        if "outputs" in resources:
            for filename, contents in resources["outputs"].items():
                print("writing: {0}".format(filename))
                with open(filename, "wb") as f:
                    f.write(contents)

        # write main file
        with open(output_file, "w") as f:
            f.write(body)

        print("Written to {0} at {1}".format(
            output_file, datetime.now(tz=None)))


class HTML_Renderer(MarkdownRenderer):
    self_reference = "render_to_html"
    exporter_class = HTMLExporter
    default_ext = ".html"
    include_input = True

    def get_config(self):
        c = Config()
        c.HTMLExporter.preprocessors = [
            ClearMetadataPreprocessor,
            ClearOutputPreprocessor,
            ExecutePreprocessor,
            CustomExtractOutputPreprocessor,
            RemoveOnContent
        ]
        c.MarkdownExporter.exclude_input = not self.include_input
        return c


def render_to_markdown(*args, **kwargs):
    return MarkdownRenderer(*args, **kwargs).process()


def render_to_html(*args, **kwargs):
    return HTML_Renderer(*args, **kwargs).process()
