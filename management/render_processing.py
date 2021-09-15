import json
from dataclasses import dataclass
from importlib import import_module
from pathlib import Path
from typing import Iterable, Optional
import shutil
import papermill as pm
import pypandoc
from jinja2 import Template
from ruamel import yaml

from . import exporters as exporters
from .upload import g_drive_upload_and_format


def add_tag_based_on_content(input_file: Path, tag: str, content: str):
    """
    not all notebook editors are good with tags, but papermill uses it
    to find the parameters cell.
    This injects tag to the file based on the content of a cell
    """
    with open(input_file) as f:
        nb = json.load(f)

    change = False
    for n, cell in enumerate(nb["cells"]):
        if cell["cell_type"] == "code":
            if cell["source"] and content in "".join(cell["source"]):
                tags = cell["metadata"].get("Tags", [])
                if tag not in tags:
                    tags.append("parameters")
                    change = True
                nb["cells"][n]["metadata"]["tags"] = tags

    if change:
        with open(input_file, "w") as f:
            json.dump(nb, f)


def render(txt: str, context: dict):
    return Template(txt).render(**context)


def combine_outputs(parts, output_path):
    text_parts = [open(p, 'r').read() for p in parts]
    result = "\n".join(text_parts)
    result = result.replace("<title>Notebook</title>", "")
    with open(output_path, 'w') as f:
        f.write(result)


@dataclass
class Notebook:
    """
    Handle talking to and rendering one file
    """
    name: str
    _parent: "Document"

    @property
    def filename(self):
        return self.name if ".ipynb" in self.name else self.name + ".ipynb"

    def raw_path(self):
        return Path("notebooks", self.filename)

    def papermill_path(self, slug: str):
        papermill_dir = Path("_render", "_papermills")
        if papermill_dir.exists() is False:
            papermill_dir.mkdir()
        return Path("_render", "_papermills", slug + "_" + self.filename)

    def papermill(self, slug, params, rerun: bool = True):
        """
        execute the notebook with the parameters
        to the papermill storage folder
        """
        # need bit here that checks the parameters are right
        actual_path = self.raw_path()
        if rerun is False:
            print("Not papermilling, just copying current file")
            shutil.copy(self.raw_path(), self.papermill_path(slug))
        else:
            add_tag_based_on_content(
                actual_path, "parameters", "#default-params")
            pm.execute_notebook(
                actual_path,
                self.papermill_path(slug),
                parameters=params
            )

    def rendered_filename(self, slug: str, ext: str = ".md"):
        """
        the location the html or file is output to
        """
        name = self._parent.name
        output_folder = Path("_render", "_parts", name, slug)
        if output_folder.exists() is False:
            output_folder.mkdir(parents=True)
        return output_folder / (self.name + ext)

    def render(self, slug: str, hide_input: bool = True):
        """
        render papermilled version to a file
        """
        include_input = not hide_input
        input_path = self.papermill_path(slug)
        exporters.render_to_markdown(
            input_path, self.rendered_filename(slug, ".md"),
            clear_and_execute=False,
            include_input=include_input)
        exporters.render_to_html(
            input_path, self.rendered_filename(slug, ".html"),
            clear_and_execute=False,
            include_input=include_input)


class Document:
    """
    Get details for a single final document (made up of several notebooks)
    """

    def __init__(self, name: str, data: dict, context: Optional[dict] = None):
        if context is None:
            context = {}
        self.name = name
        self._data = data.copy()
        self.options = {"rerun": True, "hide_input": True}
        self.options.update(self._data.get("options", {}))
        self.notebooks = [Notebook(x, _parent=self)
                          for x in self._data["notebooks"]]
        self.init_rendered_values(context)

    def init_rendered_values(self, context):
        """
        for values that are going to be populated by jinja
        this will populate/repopulate based on the currently known context
        """
        self._rendered_data = self._data.copy()
        for m_path, items in self._data["context"].items():
            mod = import_module(m_path)
            for i in items:
                context[i] = getattr(mod, i)

        self.params = self.get_rendered_parameters(context)
        rendered_properties = ["title", "slug"]
        context = {**self.params, **context}
        for r in rendered_properties:
            self._rendered_data[r] = render(self._rendered_data[r], context)
        self.slug = self._rendered_data["slug"]
        self.title = self._rendered_data["title"]

    def get(self, value: str):
        return self._data.get(value)

    def get_rendered_parameters(self, context) -> dict:
        """
        render properties using jinga
        """
        raw_params = self._data["parameters"]
        final_params = {}
        for k, v in raw_params.items():
            nv = context.get(k, render(v, context))
            final_params[k] = nv
            context[k] = nv
        return final_params

    def rendered_filename(self, ext) -> Path:
        return Path("_render", self.name, self.slug, self.slug + ext)

    def render(self, context: Optional[dict] = None):
        """
        render the the file through the respective papermills
        """

        if context is None:
            context = {}

        if context:
            self.init_rendered_values(context)

        slug = self.slug

        render_dir = Path("_render", self.name, self.slug)
        if render_dir.exists() is False:
            render_dir.mkdir(parents=True)

        # papermill and render individual notebooks
        for n in self.notebooks:
            n.papermill(self.slug, self.params, rerun=self.options["rerun"])
            n.render(self.slug, hide_input=self.options["hide_input"])

        # combine for both md and html
        for ext in [".md", ".html"]:
            dest = self.rendered_filename(ext)
            files = [x.rendered_filename(self.slug, ext)
                     for x in self.notebooks]
            combine_outputs(files, dest)
            resources_dir = files[0].parent / "_notebook_resources"
            dest_resources = dest.parent / "_notebook_resources"
            shutil.copytree(resources_dir, dest_resources, dirs_exist_ok=True)
            # copy resources folder

        # convert to docx
        input_path_html = self.rendered_filename(".html")
        output_path_doc = self.rendered_filename(".docx")
        template = Path("notebook_helper", "resources", "reference.docx")
        if template.exists() is False:
            raise ValueError("Missing Template")
        reference_doc = str(template)
        pypandoc.convert_file(str(input_path_html), 'docx', outputfile=str(
            output_path_doc), extra_args=[f"--resource-path={str(render_dir)}",
                                          f"--reference-doc={reference_doc}"])

    def upload(self):
        """
        Upload result to service (gdrive currently)
        """
        for k, v in self._data["upload"].items():
            if k == "gdrive":
                file_name = self._rendered_data["title"]
                file_path = self.rendered_filename(".docx")
                g_folder_id = v["g_folder_id"]
                g_drive_id = v["g_drive_id"]
                g_drive_upload_and_format(
                    file_name, file_path, g_folder_id, g_drive_id)


class DocumentCollection:
    """
    Collection of potential documents
    In most cases there will only be one.
    """

    @classmethod
    def from_yaml(cls, yaml_file: Path):
        with open(yaml_file) as stream:
            data = yaml.safe_load(stream)
        return cls(data)

    def __init__(self, data: dict):
        self.docs = {name: Document(name, data) for name, data in data.items()}

    def all(self) -> Iterable:
        for d in self.docs.values():
            yield d

    def first(self) -> Document:
        return list(self.docs.values())[0]

    def get(self, item: str) -> Document:
        return self.docs[item]
