from __future__ import annotations

from pathlib import Path

from data_common.dataset.settings import find_repo_root
from data_common.management.render_processing import Document, DocumentCollection


def load_document_collection(repo_root: Path | None = None) -> DocumentCollection:
    """
    Load notebook render configuration from the active dataset repository.
    """
    root = find_repo_root(repo_root)
    notebook_config = root / "notebooks" / "_render_config"
    if any(notebook_config.glob("*.yaml")):
        return DocumentCollection.from_folder(notebook_config, repo_root=root)
    render_config = root / "render.yaml"
    if render_config.is_file():
        return DocumentCollection.from_file(render_config, repo_root=root)
    return DocumentCollection({}, repo_root=root)


def selected_documents(
    collection: DocumentCollection,
    *,
    slug: str = "",
    group: str = "",
    render_all: bool = False,
) -> list[Document]:
    """
    Select configured documents for one CLI invocation.
    """
    if slug:
        return [collection.get(slug)]
    if render_all:
        return list(collection.all())
    if group:
        return list(collection.get_group(group))
    return [collection.first()]
