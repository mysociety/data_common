from __future__ import annotations

from pathlib import Path

from data_common.dataset.site import create_app
from data_common.dataset.site.settings import get_site_settings


def test_download_code_example_uses_pinned_theme_presentation(
    model_repository: Path,
) -> None:
    """
    Keep expanded code examples aligned with the former documentation theme.
    """
    app = create_app(settings=get_site_settings(repo_root=model_repository))
    client = app.test_client()

    download = client.get("/model/downloads/people-people-csv/latest")
    assert download.status_code == 200
    assert b'class="language-python"' in download.data
    assert b'class="language-bash"' in download.data
    assert b"/model/assets/css/syntax.css" in download.data
    assert b"/model/assets/js/prism.js" in download.data

    site_css = client.get("/model/assets/css/site.css")
    assert site_css.status_code == 200
    assert b"border-block: 3px solid var(--border)" in site_css.data
    assert b"border-inline-start: 0.3rem" not in site_css.data

    assert client.get("/model/assets/css/syntax.css").status_code == 200
    assert client.get("/model/assets/js/prism.js").status_code == 200
