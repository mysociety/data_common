"""
functions to export a notebook in markdown and html
"""

import json
import os
from datetime import datetime
from pathlib import Path

import nbformat
from bs4 import BeautifulSoup
from htmltabletomd import convert_table
from ipython_genutils.text import indent as normal_indent
from nbconvert import HTMLExporter, MarkdownExporter
from nbconvert.preprocessors.base import Preprocessor
from nbconvert.preprocessors.clearmetadata import ClearMetadataPreprocessor
from nbconvert.preprocessors.clearoutput import ClearOutputPreprocessor
from nbconvert.preprocessors.execute import ExecutePreprocessor
from nbconvert.preprocessors.extractoutput import ExtractOutputPreprocessor
from traitlets.config import Config  # type: ignore

notebook_render_dir = "_notebook_resources"


class RemoveOnContent(Preprocessor):
    """
    remove on some content flags
    """

    def preprocess(self, nb, resources):
        # Filter out cells that meet the conditions
        nb.cells = [
            self.preprocess_cell(cell, resources, index)[0]
            for index, cell in enumerate(nb.cells)
        ]

        return nb, resources

    def preprocess_cell(self, cell, resources, cell_index):
        """
        Apply a transformation on each cell. See base.py for details.
        """

        if cell["source"]:
            if "#HIDE" == cell["source"][:5]:
                cell.transient = {"remove_source": True}

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


def to_config(value) -> Config:
    if isinstance(value, Config):
        return value
    else:
        raise TypeError("Not a valid config (Lazy or none)")


class MarkdownRenderer(object):
    self_reference = "render_to_markdown"
    exporter_class = MarkdownExporter
    default_ext = ".md"
    clear_and_execute = True
    include_input = False
    markdown_tables = True

    def __init__(
        self,
        input_name="readme.ipynb",
        output_name=None,
        include_input=None,
        clear_and_execute=None,
    ):
        if include_input is None:
            include_input = self.__class__.include_input
        if clear_and_execute is None:
            clear_and_execute = self.__class__.clear_and_execute
        self.input_name = input_name
        self.output_name = output_name
        self.include_input = include_input
        self.clear_and_execute = clear_and_execute

    def check_for_self_reference(self, cell):
        # scope out the cell that called this function
        # prevent circular call
        contains_str = check_string_in_source(self.__class__.self_reference, cell)
        is_code = cell["cell_type"] == "code"
        return contains_str and is_code

    def get_contents(self, input_file):
        with open(input_file) as f:
            nb = json.load(f)

        nb["cells"] = [
            x
            for x in nb["cells"]
            if x["source"] and self.check_for_self_reference(x) is False
        ]

        str_notebook = json.dumps(nb)
        nb = nbformat.reads(str_notebook, as_version=4)
        return nb

    def get_config(self):
        c = Config()

        pre_processors = []

        if self.clear_and_execute:
            pre_processors += [
                ClearMetadataPreprocessor,
                ClearOutputPreprocessor,
                ExecutePreprocessor,
            ]

        pre_processors += [CustomExtractOutputPreprocessor, RemoveOnContent]

        c.MarkdownExporter = to_config(c.MarkdownExporter)

        c.MarkdownExporter.preprocessors = pre_processors
        c.MarkdownExporter.filters = {"indent": indent}
        c.MarkdownExporter.exclude_input = not self.include_input
        return c

    def process(self, input_file=None, output_file=None):
        # render clear markdown version of book
        # equiv of `jupyter nbconvert
        # --ClearMetadataPreprocessor.enabled=True
        # --ClearOutput.enabled=True
        # --no-input --execute readme.ipynb --to markdown`

        if input_file is None:
            input_file = self.input_name

        if output_file is None:
            output_file = self.output_name

        if output_file is None:
            output_file = Path(
                str(os.path.splitext(input_file)[0]) + self.__class__.default_ext
            )

        output_base_path = Path(output_file).parent

        if (output_base_path / notebook_render_dir).exists() is False:
            os.makedirs(output_base_path / notebook_render_dir)

        base = os.path.basename(input_file)
        base_root = os.path.splitext(base)[0]

        nb = self.get_contents(input_file)

        c = self.get_config()

        exporter = self.__class__.exporter_class(config=c)

        resources = {"output_files_dir": notebook_render_dir, "unique_key": base_root}

        body, resources = exporter.from_notebook_node(nb, resources)

        # write images
        if "outputs" in resources:
            for filename, contents in resources["outputs"].items():
                write_location = output_base_path / filename
                print("writing: {0}".format(write_location))
                with open(write_location, "wb") as f:
                    f.write(contents)

        if self.__class__.markdown_tables:
            body = body.replace(
                '<tr style="text-align: right;">\n      <th></th>', "<tr>"
            )
            soup = BeautifulSoup(body, "html.parser")

            for div in soup.find_all("pagebreak"):
                div.replaceWith('<div style="page-break-after: always"></div>')

            for div in soup.find_all("div"):
                table = convert_table(str(div))
                div.replaceWith(table)

            for div in soup.find_all("table"):
                table = convert_table(str(div))

                div.replaceWith(table)

            body = str(soup)
            body = body.replace("&lt;br/&gt;", "<br/>")
            body = body.replace("![png]", "![]")
            body = body.replace('<style type="text/css">', "")
            body = body.replace("</style>", "")

        # write main file
        with open(output_file, "w") as f:
            f.write(body)

        print("Written to {0} at {1}".format(output_file, datetime.now(tz=None)))


class HTML_Renderer(MarkdownRenderer):
    self_reference = "render_to_html"
    exporter_class = HTMLExporter
    default_ext = ".html"
    include_input = True
    markdown_tables = False

    def get_config(self):
        c = Config()

        pre_processors = []

        if self.clear_and_execute:
            pre_processors += [
                ClearMetadataPreprocessor,
                ClearOutputPreprocessor,
                ExecutePreprocessor,
            ]

        pre_processors += [CustomExtractOutputPreprocessor, RemoveOnContent]

        c.HTMLExporter = to_config(c.HTMLExporter)

        c.HTMLExporter.preprocessors = pre_processors

        if self.include_input is False:
            c.HTMLExporter.exclude_input = not self.include_input
            c.HTMLExporter.exclude_input_prompt = not self.include_input
            c.HTMLExporter.exclude_output_prompt = not self.include_input

        return c


def render_to_markdown(*args, **kwargs):
    return MarkdownRenderer(*args, **kwargs).process()


def render_to_html(*args, **kwargs):
    return HTML_Renderer(*args, **kwargs).process()
