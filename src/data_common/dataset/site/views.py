from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from urllib.parse import quote

from flask import (
    Blueprint,
    Response,
    abort,
    current_app,
    jsonify,
    render_template,
    send_from_directory,
)

from .catalogue import SiteCatalogue
from .models import DownloadPage
from .settings import SiteSettings

site = Blueprint("site", __name__)


def _catalogue() -> SiteCatalogue:
    return current_app.extensions["dataset_catalogue"]


def _settings() -> SiteSettings:
    return current_app.config["SITE_SETTINGS"]


@site.get("/")
def index() -> str:
    """
    Render the site landing page.
    """
    catalogue = _catalogue()
    return render_template(
        "index.html",
        datasets=catalogue.latest_datasets(),
        analyses=catalogue.analysis_pages(),
    )


@site.get("/datasets/<package>/<version>")
def dataset_page(package: str, version: str) -> str:
    """
    Render one published dataset version.
    """
    catalogue = _catalogue()
    try:
        page = catalogue.dataset(package, version)
    except KeyError:
        abort(404)

    composite_ids = {
        f"{page.name}_xlsx",
        f"{page.name}_json",
        f"{page.name}_sqlite",
    }
    composite_downloads: list[DownloadPage] = []
    resource_downloads: dict[str, list[DownloadPage]] = defaultdict(list)
    composites = page.data.custom.composite

    for download in page.downloads:
        if download.route_id in composite_ids:
            file_format = Path(download.filename).suffix.lstrip(".")
            if composites.for_format(file_format).render:
                composite_downloads.append(download)
        else:
            resource_downloads[Path(download.filename).stem].append(download)

    latest = catalogue.datasets.get((package, "latest"))
    return render_template(
        "dataset.html",
        page=page,
        latest=latest,
        composite_downloads=composite_downloads,
        explore_in_datasette=composites.for_format("sqlite").render,
        resource_downloads=resource_downloads,
    )


@site.get("/datasets/<package>/versions")
def versions_page(package: str) -> str:
    """
    Render the version listing for one dataset.
    """
    try:
        page = _catalogue().version_lists[package]
    except KeyError:
        abort(404)
    return render_template("versions.html", page=page)


@site.get("/downloads/<download_id>/<version>")
def download_page(download_id: str, version: str) -> str:
    """
    Render a gated or direct download page.
    """
    try:
        page = _catalogue().download(download_id, version)
    except KeyError:
        abort(404)

    settings = _settings()
    gate = page.download_gate_type or settings.downloads.gate
    survey = page.download_survey or settings.downloads.survey
    form_header = page.download_form_header or settings.downloads.form_header
    file_url = settings.public_url(page.file)
    survey_url = ""
    if survey:
        survey_url = (
            f"https://survey.alchemer.com/s3/{survey}"
            f"?dataset_slug={quote(page.package)}"
            f"&download_link={quote(file_url, safe='')}"
        )
    return render_template(
        "download.html",
        page=page,
        gate=gate,
        survey_url=survey_url,
        form_header=form_header,
        file_url=file_url,
    )


@site.get("/analysis/<slug>/")
def analysis_page(slug: str) -> str:
    """
    Render a published notebook analysis page.
    """
    try:
        page = _catalogue().analyses[slug]
    except KeyError:
        abort(404)
    return render_template("analysis.html", page=page)


@site.get("/analysis/<slug>/notebook_resources/<path:filename>")
def analysis_resource(slug: str, filename: str) -> Response:
    """
    Serve a resource belonging to a published notebook bundle.
    """
    try:
        page = _catalogue().analyses[slug]
    except KeyError:
        abort(404)
    resource_dir = page.bundle_dir / "notebook_resources"
    return send_from_directory(resource_dir, filename)


@site.get("/data/<path:filename>")
def published_data(filename: str) -> Response:
    """
    Serve a generated dataset publication file.
    """
    return send_from_directory(_settings().publish_dir / "data", filename)


@site.get("/data.json")
def data_index() -> Response:
    """
    Return the machine-readable dataset index.
    """
    return jsonify(_catalogue().data_index().model_dump(mode="json"))


@site.app_errorhandler(404)
def not_found(error: Exception) -> tuple[str, int]:
    """
    Render the site-local not-found page.
    """
    return render_template("error.html", status=404, message="Page not found"), 404
