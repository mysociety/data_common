from __future__ import annotations

import json
from pathlib import Path

from data_common.dataset.site import create_app
from data_common.dataset.site.freezer import build_site
from data_common.dataset.site.settings import get_site_settings


def test_site_reads_published_datasets_and_notebook_bundle(
    model_repository: Path,
) -> None:
    settings = get_site_settings(repo_root=model_repository)
    app = create_app(settings=settings)
    client = app.test_client()

    index = client.get("/model/")
    assert index.status_code == 200
    assert b"People" in index.data
    assert b"Places" in index.data
    assert b"Coverage analysis" in index.data
    assert b"<h1>Model data</h1>" in index.data
    assert b'class="ms-header__logo"' in index.data
    assert b'class="mysoc-footer"' in index.data
    assert b"Donate now" in index.data
    assert client.get("/model/assets/img/mysociety-logo.svg").status_code == 200

    dataset = client.get("/model/datasets/people/latest")
    assert dataset.status_code == 200
    assert b"Download as Excel file (xlsx)" in dataset.data
    assert b"Download Json file" in dataset.data
    assert b"Download SQLite file" in dataset.data
    assert b'class="download-button download-option"' in dataset.data
    assert b'class="field-name">id</td>' in dataset.data
    assert client.get("/model/datasets/people/versions").status_code == 200
    download = client.get("/model/downloads/people-people-csv/latest")
    assert download.status_code == 200
    assert b'class="download-button download-option download-link"' in download.data
    assert (
        client.get("/model/downloads/people-people-parquet/latest").status_code == 404
    )

    analysis = client.get("/model/analysis/coverage/")
    assert analysis.status_code == 200
    assert b"This content was exported from a notebook." in analysis.data
    assert b"notebook_resources/chart.svg" in analysis.data
    assert (
        client.get("/model/analysis/coverage/notebook_resources/chart.svg").status_code
        == 200
    )

    data_index = json.loads(client.get("/model/data.json").data)
    assert data_index["people"]["latest_version"] == "1.0.0"
    latest = data_index["people"]["versions"]["latest"]
    assert latest["full_version"] == "1.0.0"
    assert "people.csv" in latest["files"]


def test_static_build_freezes_pages_data_and_notebook_resources(
    model_repository: Path,
) -> None:
    settings = get_site_settings(repo_root=model_repository)
    report = build_site(create_app(settings=settings))

    assert report.page_count > 0
    assert (report.output_dir / "index.html").is_file()
    assert (report.output_dir / "datasets/people/latest.html").is_file()
    assert (report.output_dir / "analysis/coverage/index.html").is_file()
    assert (
        report.output_dir / "analysis/coverage/notebook_resources/chart.svg"
    ).is_file()
    assert (report.output_dir / "data/people/latest/people.csv").is_file()
    assert (report.output_dir / "data.json").is_file()
    assert (report.output_dir / "assets/img/mysociety-logo.svg").is_file()
    assert (report.output_dir / "assets/css/syntax.css").is_file()
    assert (report.output_dir / "assets/js/prism.js").is_file()
    assert (report.output_dir / ".nojekyll").is_file()
