from __future__ import annotations

import json
from pathlib import Path

import nbformat
import pytest
from pydantic import ValidationError

from data_common.dataset.site.catalogue import SiteCatalogue
from data_common.dataset.site.notebook import publish_analysis_bundle
from data_common.dataset.site.schemas import AnalysisBundleMetadata
from data_common.dataset.site.settings import get_site_settings
from data_common.management.exporters import HTMLRenderer


def test_notebook_export_creates_bundle_consumed_by_dataset_site(
    model_repository: Path,
    notebook_file: Path,
    tmp_path: Path,
) -> None:
    rendered = tmp_path / "rendered" / "analysis.html"
    HTMLRenderer(
        input_name=notebook_file,
        output_name=rendered,
        clear_and_execute=False,
        include_input=False,
    ).process()

    resources = rendered.parent / "_notebook_resources"
    extracted_images = list(resources.glob("*.png"))
    assert extracted_images
    assert "_notebook_resources/" in rendered.read_text()

    settings = get_site_settings(repo_root=model_repository)
    bundle = publish_analysis_bundle(
        source_file=rendered,
        resources_dir=resources,
        settings=settings,
        slug="notebook-export",
        title="Notebook export",
        metadata=AnalysisBundleMetadata(
            description="Created from the saved notebook fixture.",
            order=2,
        ),
    )

    metadata = json.loads((bundle / "page.json").read_text())
    assert metadata["schema_version"] == 1
    assert metadata["kind"] == "analysis"
    assert metadata["slug"] == "notebook-export"
    assert "_notebook_resources/" not in (bundle / "body.html").read_text()
    assert list((bundle / "notebook_resources").glob("*.png"))

    page = SiteCatalogue(settings).analyses["notebook-export"]
    assert page.title == "Notebook export"
    assert "Model analysis" in page.body_html


def test_notebook_bundle_rejects_a_slug_outside_the_bundle_directory(
    model_repository: Path,
    tmp_path: Path,
) -> None:
    settings = get_site_settings(repo_root=model_repository)
    source = tmp_path / "analysis.html"
    source.write_text("<p>Analysis</p>")
    protected = settings.analysis.bundle_dir.parent / "protected"
    protected.mkdir(parents=True)
    marker = protected / "marker.txt"
    marker.write_text("keep")

    with pytest.raises(ValidationError):
        publish_analysis_bundle(
            source_file=source,
            resources_dir=tmp_path / "resources",
            settings=settings,
            slug="../protected",
            title="Unsafe",
        )

    assert marker.read_text() == "keep"


@pytest.mark.notebook
def test_notebook_export_executes_code_before_rendering(tmp_path: Path) -> None:
    """
    Prove the exporter executes a clean notebook through a real kernel.
    """
    notebook_path = tmp_path / "execute.ipynb"
    output_path = tmp_path / "rendered" / "execute.html"
    notebook = nbformat.v4.new_notebook(
        cells=[
            nbformat.v4.new_code_cell(
                "message = 'created by notebook execution'\nprint(message)"
            )
        ],
        metadata={
            "kernelspec": {
                "display_name": "Python 3",
                "language": "python",
                "name": "python3",
            }
        },
    )
    nbformat.write(notebook, notebook_path)

    HTMLRenderer(
        input_name=notebook_path,
        output_name=output_path,
        clear_and_execute=True,
        include_input=False,
    ).process()

    assert "created by notebook execution" in output_path.read_text()
