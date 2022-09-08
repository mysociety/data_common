from __future__ import annotations
import json
import shutil
from copy import deepcopy
from dataclasses import dataclass
from importlib import import_module
from pathlib import Path
from typing import Iterable, Optional, Any, Type
from bs4 import BeautifulSoup, Tag

import papermill as pm  # type: ignore
import pypandoc  # type: ignore
from jinja2 import Template
from ruamel import yaml  # type: ignore

from . import exporters as exporters
from .upload import g_drive_upload_and_format
from ..dataset.jekyll_management import markdown_with_frontmatter


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


def render(txt: str, context: dict[str, Any]):
    t = Template(str(txt))
    return t.render(**context)


def combine_outputs(parts: list[Path], output_path: Path):
    text_parts = [open(p, "r").read() for p in parts]
    result = "\n".join(text_parts)
    result = result.replace("<title>Notebook</title>", "")
    with open(output_path, "w") as f:
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

    def papermill(self, slug: str, params: dict[str, Any], rerun: bool = True):
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
            add_tag_based_on_content(actual_path, "parameters", "#default-params")
            pm.execute_notebook(  # type: ignore
                actual_path, self.papermill_path(slug), parameters=params
            )

    def rendered_filename(self, slug: str, ext: str = ".md") -> Path:
        """
        the location the html or file is output to
        """
        name = self._parent.name
        output_folder = Path("_render", "_parts", name, slug)
        if output_folder.exists() is False:
            output_folder.mkdir(parents=True)
        return output_folder / (self.name + ext)

    def fix_html(self, filename: Path):
        """
        Remove unnecessary formatting from html documents
        """
        content = filename.read_text()
        soup = BeautifulSoup(content, "lxml")
        for div in soup.find_all("a", {"class": "anchor-link"}):
            div.decompose()
        body = soup.find("body")
        if not isinstance(body, Tag):
            raise ValueError("body is not being read correctly")
        contents = body.decode_contents()
        with open(filename, "w") as f:
            f.write(contents)

    def render(self, slug: str, hide_input: bool = True):
        """
        render papermilled version to a file
        """
        include_input = not hide_input
        input_path = self.papermill_path(slug)
        exporters.render_to_markdown(  # type: ignore
            input_path,
            self.rendered_filename(slug, ".md"),
            clear_and_execute=False,
            include_input=include_input,
        )
        exporters.render_to_html(  # type: ignore
            input_path,
            self.rendered_filename(slug, ".html"),
            clear_and_execute=False,
            include_input=include_input,
        )
        self.fix_html(self.rendered_filename(slug, ".html"))


class Document:
    """
    Get details for a single final document (made up of several notebooks)
    """

    def __init__(
        self, name: str, data: dict[str, Any], context: Optional[dict[str, Any]] = None
    ):
        if context is None:
            context = {}
        self.name = name
        self._data = data.copy()
        self.options = {"rerun": True, "hide_input": True}
        self.options.update(self._data.get("options", {}))
        self.notebooks = [Notebook(x, _parent=self) for x in self._data["notebooks"]]
        self.init_rendered_values(context)

    def init_rendered_values(self, context: dict[str, Any]):
        """
        for values that are going to be populated by jinja
        this will populate/repopulate based on the currently known context
        """
        self._rendered_data = self._data.copy()
        for m_path, items in self._data.get("context", {}).items():
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

    def get_rendered_parameters(self, context: dict[str, Any]) -> dict[str, str]:
        """
        render properties using jinga
        """
        raw_params = self._data.get("parameters", {})
        final_params: dict[str, str] = {}
        for k, v in raw_params.items():
            nv = context.get(k, render(v, context))
            final_params[k] = nv
            context[k] = nv
        return final_params

    def rendered_filename(self, ext: str) -> Path:
        return Path("_render", self.name, self.slug, self.slug + ext)

    def render(self, context: Optional[dict[str, Any]] = None):
        """
        render the the file through the respective papermills
        """

        if context is None:
            context = {}

        if context:
            self.init_rendered_values(context)

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
            files = [x.rendered_filename(self.slug, ext) for x in self.notebooks]
            combine_outputs(files, dest)
            resources_dir = files[0].parent / "_notebook_resources"
            dest_resources = dest.parent / "_notebook_resources"
            shutil.copytree(resources_dir, dest_resources, dirs_exist_ok=True)
            # copy resources folder

        # convert to docx
        input_path_html = self.rendered_filename(".html")
        output_path_doc = self.rendered_filename(".docx")
        template = Path(
            "src", "data_common", "src", "data_common", "resources", "reference.docx"
        )
        if template.exists() is False:
            raise ValueError("Missing Template")
        reference_doc = str(template)
        print(input_path_html)
        pypandoc.convert_file(  # type: ignore
            str(input_path_html),
            "docx",
            outputfile=str(output_path_doc),
            extra_args=[
                f"--resource-path={str(render_dir)}",
                f"--reference-doc={reference_doc}",
            ],
        )

    def upload(self, context: Optional[dict[str, Any]] = None):
        """
        Upload result to service
        """

        if context:
            self.init_rendered_values(context)

        for k, v in self._data["upload"].items():
            if v is None:
                v = {}
            if k == "readme":
                print("Publishing to readme")
                source_file = self.rendered_filename(".md")
                contents = source_file.read_text().replace(
                    "_notebook_resources", "_readme_resources"
                )
                readme = Path("readme.md")
                if readme.exists() is False:
                    raise ValueError("readme.md not found")
                readme_contents = readme.read_text()
                start_anchor = v.get("start", "")
                end_anchor = v.get("end", "")
                if start_anchor:
                    start_text = readme_contents.find(start_anchor)
                else:
                    start_text = 0

                if end_anchor:
                    end_text = readme_contents.find(end_anchor, start_text)
                else:
                    end_text = len(readme_contents)
                new_content = (
                    readme_contents[: start_text + len(start_anchor)]
                    + contents
                    + readme_contents[end_text:]
                )
                with open(readme, "w") as f:
                    f.write(new_content)
                shutil.copytree(
                    source_file.parent / "_notebook_resources",
                    "_readme_resources",
                    dirs_exist_ok=True,
                )
            if k == "gdrive":
                file_name = self._rendered_data["title"]
                file_path = self.rendered_filename(".docx")
                g_drive_upload_and_format(
                    file_name=file_name,
                    file_path=file_path,
                    drive_name=v.get("g_drive_name", None),
                    drive_id=v.get("g_drive_id", None),
                    folder_path=v.get("g_folder_name", None),
                    folder_id=v.get("g_folder_id", None),
                )
            if k == "jekyll":
                print("Publishing to Jekyll dir")
                if v:
                    front_matter = v
                else:
                    front_matter = {}
                front_matter["title"] = self._rendered_data["title"]
                analysis = Path("docs", "_analysis")
                if analysis.exists() is False:
                    analysis.mkdir()
                dest = analysis / (self._rendered_data["slug"] + ".html")
                source_file = self.rendered_filename(".html")
                contents = source_file.read_text()
                contents = contents.replace("_notebook_resources", "notebook_resources")
                markdown_with_frontmatter(front_matter, dest, contents)
                shutil.copytree(
                    source_file.parent / "_notebook_resources",
                    analysis / "notebook_resources",
                    dirs_exist_ok=True,
                )


class DocumentCollection:
    """
    Collection of potential documents.
    In most cases there will only be one.
    """

    @classmethod
    def from_folder(cls: Type[DocumentCollection], dir: Path) -> DocumentCollection:
        yaml_files = dir.glob("*.yaml")
        all_docs = {}
        for y in yaml_files:
            with open(y) as stream:
                data: dict[str, Any]
                data = yaml.safe_load(stream)  # type: ignore
            all_docs[y.stem] = data
        return cls(all_docs)

    def __init__(self, data: dict[str, Any]):

        for k, v in data.items():
            if "meta" not in v:
                data[k]["meta"] = False
            if "extends" in v:
                base = deepcopy(data[v["extends"]])
                if "meta" in base:
                    base.pop("meta")
                base.update(v)
                base.pop("extends")
                data[k] = base

        for k, v in data.items():
            if "group" not in v:
                data[k]["group"] = None

        self.docs = {name: Document(name, data) for name, data in data.items()}

    def all(self) -> Iterable[Any]:
        for d in self.docs.values():
            if d._data["meta"] is False:  # type: ignore
                yield d

    def get_group(self, group: str) -> Iterable[Any]:
        for d in self.all():
            if d._data["group"] == group:
                yield d

    def first(self) -> Document:
        return list(self.docs.values())[0]

    def get(self, item: str) -> Document:
        return self.docs[item]
