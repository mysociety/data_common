from __future__ import annotations

import shutil
import warnings
from collections.abc import Iterable, Mapping
from copy import deepcopy
from importlib import import_module
from importlib.resources import as_file, files
from pathlib import Path
from typing import Any, Self

import pypandoc  # type: ignore[import-untyped]
from jinja2 import Template
from ruamel.yaml import YAML

from ..dataset.site.notebook import publish_analysis_bundle
from ..dataset.site.schemas import AnalysisBundleMetadata
from ..dataset.site.settings import get_site_settings
from .notebook_rendering import Notebook, combine_outputs
from .render_models import DocumentDefinition, RenderedDocument


def render_value(value: object, context: Mapping[str, Any]) -> str:
    """
    Render one configured string using the current document context.
    """
    return Template(str(value)).render(**context)


def convert_to_docx(
    input_path: Path,
    output_path: Path,
    resource_dir: Path,
) -> None:
    """
    Convert rendered HTML to DOCX using the packaged reference document.
    """
    reference = files("data_common").joinpath("resources", "reference.docx")
    with as_file(reference) as reference_path:
        if not reference_path.is_file():
            raise ValueError("Missing packaged DOCX reference template")
        pypandoc.convert_file(  # type: ignore[no-untyped-call]
            str(input_path),
            "docx",
            outputfile=str(output_path),
            extra_args=[
                f"--resource-path={resource_dir}",
                f"--reference-doc={reference_path}",
            ],
        )


class Document:
    """
    Render and publish a configured document made from one or more notebooks.
    """

    def __init__(
        self,
        name: str,
        definition: DocumentDefinition,
        *,
        repo_root: Path,
        context: Mapping[str, Any] | None = None,
    ) -> None:
        self.name = name
        self.definition = definition
        self.repo_root = repo_root
        self.notebooks = [
            Notebook(notebook, document_name=name, repo_root=repo_root)
            for notebook in definition.notebooks
        ]
        self.rendered = self.rendered_values(context or {})
        self.params = self.rendered.parameters
        self.slug = self.rendered.slug
        self.title = self.rendered.title

    def rendered_values(self, context: Mapping[str, Any]) -> RenderedDocument:
        """
        Resolve imported context, parameters, title, and slug.
        """
        rendered_context = dict(context)
        for module_path, names in self.definition.context.items():
            module = import_module(module_path)
            for name in names:
                rendered_context[name] = getattr(module, name)

        parameters = self.rendered_parameters(rendered_context)
        complete_context = {**parameters, **rendered_context}
        return RenderedDocument(
            title=render_value(self.definition.title, complete_context),
            slug=render_value(self.definition.slug, complete_context),
            parameters=parameters,
        )

    def apply_context(self, context: Mapping[str, Any]) -> None:
        """
        Re-render context-sensitive document attributes.
        """
        self.rendered = self.rendered_values(context)
        self.params = self.rendered.parameters
        self.slug = self.rendered.slug
        self.title = self.rendered.title

    def get(self, value: str) -> object:
        """
        Return an optional extension value from the document definition.
        """
        return getattr(self.definition, value, None)

    def rendered_parameters(self, context: dict[str, Any]) -> dict[str, Any]:
        """
        Render configured parameters in declaration order.
        """
        final_params: dict[str, Any] = {}
        for key, value in self.definition.parameters.items():
            rendered = context.get(key, render_value(value, context))
            final_params[key] = rendered
            context[key] = rendered
        return final_params

    def rendered_filename(self, extension: str) -> Path:
        """
        Return the combined document output path.
        """
        return (
            self.repo_root
            / "_render"
            / self.name
            / self.slug
            / f"{self.slug}{extension}"
        )

    def render(self, context: Mapping[str, Any] | None = None) -> None:
        """
        Execute constituent notebooks and produce combined document formats.
        """
        if context:
            self.apply_context(context)

        render_dir = self.rendered_filename(".html").parent
        render_dir.mkdir(parents=True, exist_ok=True)

        for notebook in self.notebooks:
            notebook.papermill(
                self.slug,
                self.params,
                rerun=self.definition.options.rerun,
            )
            notebook.render(
                self.slug,
                hide_input=self.definition.options.hide_input,
            )

        for extension in (".md", ".html"):
            destination = self.rendered_filename(extension)
            fragments = [
                notebook.rendered_filename(self.slug, extension)
                for notebook in self.notebooks
            ]
            combine_outputs(fragments, destination)
            resources_dir = fragments[0].parent / "_notebook_resources"
            if resources_dir.exists():
                shutil.copytree(
                    resources_dir,
                    destination.parent / "_notebook_resources",
                    dirs_exist_ok=True,
                )

        convert_to_docx(
            self.rendered_filename(".html"),
            self.rendered_filename(".docx"),
            render_dir,
        )

    def upload(self, context: Mapping[str, Any] | None = None) -> None:
        """
        Publish rendered output to all configured destinations.
        """
        if context:
            self.apply_context(context)

        for target, target_config in self.definition.upload.root.items():
            config = target_config or {}
            if target == "readme":
                self.publish_readme(config)
            elif target == "gdrive":
                self.publish_google_drive(config)
            elif target in {"site", "jekyll"}:
                self.publish_site(config, legacy_target=target == "jekyll")

    def publish_readme(self, config: Mapping[str, Any]) -> None:
        """
        Replace a configured section of the repository README.
        """
        print("Publishing to readme")
        source_file = self.rendered_filename(".md")
        contents = source_file.read_text().replace(
            "_notebook_resources",
            "_readme_resources",
        )
        readme = self.repo_root / "readme.md"
        if not readme.is_file():
            raise ValueError("readme.md not found")
        readme_contents = readme.read_text()
        start_anchor = str(config.get("start", ""))
        end_anchor = str(config.get("end", ""))
        start_text = readme_contents.find(start_anchor) if start_anchor else 0
        end_text = (
            readme_contents.find(end_anchor, start_text)
            if end_anchor
            else len(readme_contents)
        )
        new_content = (
            readme_contents[: start_text + len(start_anchor)]
            + contents
            + readme_contents[end_text:]
        )
        readme.write_text(new_content)
        resources = source_file.parent / "_notebook_resources"
        if resources.exists():
            shutil.copytree(
                resources,
                self.repo_root / "_readme_resources",
                dirs_exist_ok=True,
            )

    def publish_google_drive(self, config: Mapping[str, Any]) -> None:
        """
        Upload the rendered DOCX file to Google Drive.
        """
        from .upload import g_drive_upload_and_format

        g_drive_upload_and_format(
            file_name=self.title,
            file_path=self.rendered_filename(".docx"),
            drive_name=config.get("g_drive_name"),
            drive_id=config.get("g_drive_id"),
            folder_path=config.get("g_folder_name"),
            folder_id=config.get("g_folder_id"),
        )

    def publish_site(
        self,
        config: Mapping[str, Any],
        *,
        legacy_target: bool = False,
    ) -> None:
        """
        Publish the rendered HTML and resources as a dataset-site bundle.
        """
        if legacy_target:
            warnings.warn(
                "The notebook upload target 'jekyll' is deprecated; "
                "use 'site' instead.",
                DeprecationWarning,
                stacklevel=2,
            )
        print("Publishing analysis bundle for the dataset site")
        source_file = self.rendered_filename(".html")
        publish_analysis_bundle(
            source_file=source_file,
            resources_dir=source_file.parent / "_notebook_resources",
            settings=get_site_settings(repo_root=self.repo_root),
            slug=self.slug,
            title=self.title,
            metadata=AnalysisBundleMetadata.model_validate(config),
        )


class DocumentCollection:
    """
    Validate and expose all notebook documents configured in a repository.
    """

    @classmethod
    def from_file(
        cls,
        path: Path,
        *,
        repo_root: Path | None = None,
    ) -> Self:
        """
        Load a collection from one YAML file.
        """
        with path.open() as stream:
            value = YAML(typ="safe", pure=True).load(stream)
        data = value if isinstance(value, dict) else {}
        return cls(data, repo_root=repo_root or path.parent)

    @classmethod
    def from_folder(
        cls,
        directory: Path,
        *,
        repo_root: Path | None = None,
    ) -> Self:
        """
        Load a collection from all YAML files in a directory.
        """
        data: dict[str, Any] = {}
        loader = YAML(typ="safe", pure=True)
        for yaml_file in sorted(directory.glob("*.yaml")):
            with yaml_file.open() as stream:
                data[yaml_file.stem] = loader.load(stream)
        return cls(data, repo_root=repo_root or Path.cwd())

    def __init__(
        self,
        data: Mapping[str, Any],
        *,
        repo_root: Path | None = None,
    ) -> None:
        self.repo_root = (repo_root or Path.cwd()).resolve()
        resolved = self.resolve_definitions(data)
        self.docs = {
            name: Document(
                name,
                DocumentDefinition.model_validate(definition),
                repo_root=self.repo_root,
            )
            for name, definition in resolved.items()
        }

    @staticmethod
    def resolve_definitions(
        data: Mapping[str, Any],
    ) -> dict[str, dict[str, Any]]:
        """
        Apply document inheritance before validating each definition.
        """
        resolved: dict[str, dict[str, Any]] = {}
        for name, raw_definition in data.items():
            if not isinstance(raw_definition, Mapping):
                raise TypeError(f"Document {name!r} must be a mapping")
            definition = dict(raw_definition)
            parent_name = definition.get("extends")
            if parent_name:
                parent = data.get(str(parent_name))
                if not isinstance(parent, Mapping):
                    raise ValueError(
                        f"Document {name!r} extends unknown document {parent_name!r}"
                    )
                inherited = deepcopy(dict(parent))
                inherited.pop("meta", None)
                inherited.update(definition)
                definition = inherited
            definition.pop("extends", None)
            resolved[str(name)] = definition
        return resolved

    def all(self) -> Iterable[Document]:
        """
        Yield documents not marked as configuration-only metadata.
        """
        return (
            document for document in self.docs.values() if not document.definition.meta
        )

    def get_group(self, group: str) -> Iterable[Document]:
        """
        Yield publishable documents belonging to a named group.
        """
        return (
            document for document in self.all() if document.definition.group == group
        )

    def first(self) -> Document:
        """
        Return the first configured document.
        """
        try:
            return next(iter(self.docs.values()))
        except StopIteration as error:
            raise ValueError("No notebook documents are configured") from error

    def get(self, item: str) -> Document:
        """
        Return a configured document by name.
        """
        return self.docs[item]
