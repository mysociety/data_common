from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

import nbformat
import papermill as pm  # type: ignore[import-untyped]
from bs4 import BeautifulSoup, Tag

from . import exporters


def add_tag_based_on_content(input_file: Path, tag: str, content: str) -> None:
    """
    Add a notebook cell tag when its source contains a marker string.
    """
    notebook = nbformat.read(input_file, as_version=4)
    changed = False
    for cell in notebook.cells:
        if cell.cell_type != "code" or content not in cell.source:
            continue
        tags = list(cell.metadata.get("tags", []))
        if tag not in tags:
            tags.append(tag)
            cell.metadata["tags"] = tags
            changed = True
    if changed:
        nbformat.write(notebook, input_file)


def combine_outputs(parts: list[Path], output_path: Path) -> None:
    """
    Combine rendered notebook fragments into one output document.
    """
    result = "\n".join(part.read_text() for part in parts)
    output_path.write_text(result.replace("<title>Notebook</title>", ""))


class Notebook:
    """
    Execute and render one notebook belonging to a configured document.
    """

    def __init__(self, name: str, document_name: str, repo_root: Path) -> None:
        self.name = name
        self.document_name = document_name
        self.repo_root = repo_root

    @property
    def filename(self) -> str:
        """
        Return the notebook filename with its expected extension.
        """
        return self.name if self.name.endswith(".ipynb") else self.name + ".ipynb"

    def raw_path(self) -> Path:
        """
        Return the source notebook path in the dataset repository.
        """
        return self.repo_root / "notebooks" / self.filename

    def papermill_path(self, slug: str) -> Path:
        """
        Return the executed notebook cache path.
        """
        papermill_dir = self.repo_root / "_render" / "_papermills"
        papermill_dir.mkdir(parents=True, exist_ok=True)
        return papermill_dir / f"{slug}_{self.filename}"

    def papermill(
        self,
        slug: str,
        params: dict[str, Any],
        rerun: bool = True,
    ) -> None:
        """
        Execute the notebook or copy its existing outputs to the render cache.
        """
        actual_path = self.raw_path()
        if not rerun:
            print("Not papermilling, just copying current file")
            shutil.copy(actual_path, self.papermill_path(slug))
            return

        add_tag_based_on_content(actual_path, "parameters", "#default-params")
        pm.execute_notebook(  # type: ignore[no-untyped-call]
            actual_path,
            self.papermill_path(slug),
            parameters=params,
            kernel_name="python3",
        )

    def rendered_filename(self, slug: str, extension: str = ".md") -> Path:
        """
        Return the destination of one rendered notebook fragment.
        """
        output_folder = (
            self.repo_root / "_render" / "_parts" / self.document_name / slug
        )
        output_folder.mkdir(parents=True, exist_ok=True)
        return output_folder / f"{self.name}{extension}"

    def fix_html(self, filename: Path) -> None:
        """
        Reduce a full notebook export to HTML body contents.
        """
        soup = BeautifulSoup(filename.read_text(), "lxml")
        for anchor in soup.find_all("a", {"class": "anchor-link"}):
            anchor.decompose()
        body = soup.find("body")
        if not isinstance(body, Tag):
            raise TypeError("body is not being read correctly")
        filename.write_text(body.decode_contents())

    def render(self, slug: str, hide_input: bool = True) -> None:
        """
        Render the executed notebook to Markdown and HTML fragments.
        """
        include_input = not hide_input
        input_path = self.papermill_path(slug)
        exporters.render_to_markdown(
            input_path,
            self.rendered_filename(slug, ".md"),
            clear_and_execute=False,
            include_input=include_input,
        )
        exporters.render_to_html(
            input_path,
            self.rendered_filename(slug, ".html"),
            clear_and_execute=False,
            include_input=include_input,
        )
        self.fix_html(self.rendered_filename(slug, ".html"))
