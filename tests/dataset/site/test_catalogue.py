from __future__ import annotations

import json
from pathlib import Path

import pytest

from data_common.dataset.site.catalogue import SiteCatalogue
from data_common.dataset.site.settings import get_site_settings


def test_catalogue_applies_defaults_to_minimal_dataset(
    model_repository: Path,
) -> None:
    catalogue = SiteCatalogue(get_site_settings(repo_root=model_repository))

    places = catalogue.dataset("places", "latest")
    assert places.data.custom.formats.model_dump() == {
        "csv": True,
        "parquet": True,
        "geojson": False,
        "gpkg": False,
    }
    assert [page.name for page in catalogue.latest_datasets()] == ["people", "places"]
    assert [page.slug for page in catalogue.analysis_pages()] == ["coverage"]


def test_catalogue_rejects_unsupported_notebook_bundle_schema(
    model_repository: Path,
) -> None:
    metadata = model_repository / "_render/site/analysis/coverage/page.json"
    contents = json.loads(metadata.read_text())
    contents["schema_version"] = 2
    metadata.write_text(json.dumps(contents))

    with pytest.raises(ValueError, match="Unsupported analysis schema"):
        SiteCatalogue(get_site_settings(repo_root=model_repository))
