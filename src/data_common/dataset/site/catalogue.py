from __future__ import annotations

from collections import defaultdict
from typing import NamedTuple

from pydantic import ValidationError

from .models import (
    AnalysisPage,
    DataIndex,
    DataIndexFile,
    DataIndexVersion,
    DatasetDataIndex,
    DatasetVersion,
    DatasetVersionList,
    DownloadPage,
    PublishedDataset,
    VersionLabels,
)
from .schemas import AnalysisBundleManifest
from .settings import SiteSettings


class SemanticVersionKey(NamedTuple):
    """
    Provide a sortable representation of a semantic version string.
    """

    major: int
    minor: int
    patch: int
    suffix: str


def semantic_version_key(value: str) -> SemanticVersionKey:
    """
    Convert a semantic version string into a stable sorting key.
    """
    base, _, suffix = value.partition("-")
    try:
        major, minor, patch = (int(part) for part in base.split("."))
    except (TypeError, ValueError):
        return SemanticVersionKey(-1, -1, -1, value)
    return SemanticVersionKey(major, minor, patch, suffix)


class SiteCatalogue:
    """
    Load and index the published datasets and analysis bundles for a site.
    """

    def __init__(self, settings: SiteSettings) -> None:
        self.settings = settings
        self.datasets: dict[tuple[str, str], DatasetVersion] = {}
        self.downloads: dict[tuple[str, str], DownloadPage] = {}
        self.version_lists: dict[str, DatasetVersionList] = {}
        self.analyses: dict[str, AnalysisPage] = {}
        self.load_datasets()
        self.load_analyses()

    def load_datasets(self) -> None:
        """
        Load all published datapackages and derive their download pages.
        """
        data_dir = self.settings.publish_dir / "data"
        versions_by_name: dict[str, list[DatasetVersion]] = defaultdict(list)

        for package_file in sorted(data_dir.glob("*/*/datapackage.json")):
            data = PublishedDataset.model_validate_json(package_file.read_text())
            label = package_file.parent.name
            full_version = data.version or label
            page = DatasetVersion(
                name=data.name,
                title=data.title or data.name,
                description=data.description,
                version=label,
                full_version=full_version,
                data=data,
            )
            page.downloads = self.downloads_for(page)
            self.datasets[(page.name, page.route_version)] = page
            versions_by_name[page.name].append(page)
            for download in page.downloads:
                self.downloads[(download.route_id, download.route_version)] = download

        for name, pages in versions_by_name.items():
            grouped: dict[str, list[str]] = defaultdict(list)
            for page in pages:
                grouped[page.full_version].append(page.version)
            versions = [
                VersionLabels(full_version, tuple(sorted(labels)))
                for full_version, labels in sorted(
                    grouped.items(),
                    key=lambda item: semantic_version_key(item[0]),
                    reverse=True,
                )
            ]
            self.version_lists[name] = DatasetVersionList(
                name=name,
                title=pages[0].title,
                versions=versions,
            )

    def downloads_for(self, page: DatasetVersion) -> list[DownloadPage]:
        """
        Return download pages for files that exist in one published version.
        """
        results: list[DownloadPage] = []
        version_dir = self.settings.publish_dir / "data" / page.name / page.version
        overrides = page.data.custom.download_options
        gate = None if overrides.gate == "default" else overrides.gate
        survey = None if overrides.survey == "default" else overrides.survey
        header = None if overrides.header_text == "default" else overrides.header_text

        for resource in page.data.resources:
            for format_option in page.data.custom.formats.options():
                if not format_option.enabled:
                    continue
                route_id = (
                    f"{page.name}-{resource.name}-{format_option.name}"
                ).replace("_", "-")
                path = resource.path
                stem = path[: path.rfind(".")] if "." in path else path
                filename = f"{stem}.{format_option.name}"
                if not (version_dir / filename).is_file():
                    continue
                results.append(
                    DownloadPage(
                        route_id=route_id,
                        package=page.name,
                        package_title=page.title,
                        title=resource.title or resource.name,
                        filename=filename,
                        version=page.version,
                        full_version=page.full_version,
                        file=f"/data/{page.name}/{page.version}/{filename}",
                        package_route=page.route_version,
                        download_gate_type=gate,
                        download_survey=survey,
                        download_form_header=header,
                    )
                )

        for data_format in ("xlsx", "json", "sqlite"):
            route_id = f"{page.name}_{data_format}"
            filename = f"{page.name}.{data_format}"
            if not (version_dir / filename).is_file():
                continue
            results.append(
                DownloadPage(
                    route_id=route_id,
                    package=page.name,
                    package_title=page.title,
                    title=filename,
                    filename=filename,
                    version=page.version,
                    full_version=page.full_version,
                    file=f"/data/{page.name}/{page.version}/{filename}",
                    package_route=page.route_version,
                    download_gate_type=gate,
                    download_survey=survey,
                    download_form_header=header,
                )
            )

        return results

    def load_analyses(self) -> None:
        """
        Load and validate all configured notebook analysis bundles.
        """
        if not self.settings.analysis.enabled:
            return
        bundle_root = self.settings.analysis.bundle_dir
        if not bundle_root.exists():
            return

        for metadata_file in sorted(bundle_root.glob("*/page.json")):
            try:
                manifest = AnalysisBundleManifest.model_validate_json(
                    metadata_file.read_text()
                )
            except ValidationError as error:
                raise ValueError(
                    f"Unsupported analysis schema in {metadata_file}: {error}"
                ) from error

            bundle_dir = metadata_file.parent
            if manifest.slug != bundle_dir.name:
                raise ValueError(
                    f"Analysis slug {manifest.slug!r} does not match {bundle_dir.name!r}"
                )
            body_file = bundle_dir / "body.html"
            if not body_file.exists():
                raise ValueError(f"Missing analysis body: {body_file}")
            self.analyses[manifest.slug] = AnalysisPage(
                manifest=manifest,
                body_html=body_file.read_text(),
                bundle_dir=bundle_dir,
            )

    def dataset(self, package: str, version: str) -> DatasetVersion:
        """
        Return a published dataset version by route identifiers.
        """
        return self.datasets[(package, version)]

    def download(self, route_id: str, version: str) -> DownloadPage:
        """
        Return a download page by route identifiers.
        """
        return self.downloads[(route_id, version)]

    def latest_datasets(self) -> list[DatasetVersion]:
        """
        Return latest dataset aliases in their configured display order.
        """
        pages = [page for page in self.datasets.values() if page.is_latest]
        return sorted(pages, key=lambda page: page.data.custom.dataset_order)

    def analysis_pages(self) -> list[AnalysisPage]:
        """
        Return analysis pages in their configured display order.
        """
        return sorted(self.analyses.values(), key=lambda page: (page.order, page.title))

    def data_index(self) -> DataIndex:
        """
        Build the typed public data.json index.
        """
        result: dict[str, DatasetDataIndex] = {}
        for name in sorted(self.version_lists):
            versions: dict[str, DataIndexVersion] = {}
            pages = sorted(
                (page for page in self.datasets.values() if page.name == name),
                key=lambda page: page.version,
            )
            for page in pages:
                files = {
                    "datapackage.json": DataIndexFile(
                        url=self.settings.public_url(
                            f"data/{name}/{page.version}/datapackage.json"
                        ),
                        survey_link=self.settings.public_url(
                            f"datasets/{name}/{page.route_version}"
                        ),
                    )
                }
                for download in page.downloads:
                    files[download.filename] = DataIndexFile(
                        url=self.settings.public_url(download.file),
                        survey_link=self.settings.public_url(
                            "downloads/"
                            f"{download.route_id}/{download.route_version}#survey"
                        ),
                    )
                versions[page.version] = DataIndexVersion(
                    full_version=page.full_version,
                    files=files,
                )
            latest = next(
                (page.full_version for page in pages if page.version == "latest"),
                "",
            )
            result[name] = DatasetDataIndex(
                latest_version=latest,
                versions=versions,
            )
        return DataIndex(result)
