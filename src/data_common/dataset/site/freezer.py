from __future__ import annotations

import shutil
from html.parser import HTMLParser
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import urlsplit

from flask import Flask

from .catalogue import SiteCatalogue
from .models import BuildReport, BuildTarget, DataIndex, MissingLink
from .settings import SiteSettings, get_site_settings


def build_targets(
    catalogue: SiteCatalogue,
    settings: SiteSettings,
) -> list[BuildTarget]:
    """
    Return every application route and its static output destination.
    """
    targets = [BuildTarget(settings.site_path(), Path("index.html"))]

    for page in catalogue.datasets.values():
        targets.append(
            BuildTarget(
                settings.site_path(
                    f"datasets/{page.name}/{page.route_version}",
                ),
                Path("datasets", page.name, f"{page.route_version}.html"),
            )
        )

    for page in catalogue.version_lists.values():
        targets.append(
            BuildTarget(
                settings.site_path(f"datasets/{page.name}/versions"),
                Path("datasets", page.name, "versions.html"),
            )
        )

    for page in catalogue.downloads.values():
        targets.append(
            BuildTarget(
                settings.site_path(
                    f"downloads/{page.route_id}/{page.route_version}",
                ),
                Path(
                    "downloads",
                    page.route_id,
                    f"{page.route_version}.html",
                ),
            )
        )

    for page in catalogue.analyses.values():
        targets.append(
            BuildTarget(
                settings.site_path(f"analysis/{page.slug}/"),
                Path("analysis", page.slug, "index.html"),
            )
        )

    targets.append(
        BuildTarget(
            settings.site_path("data.json"),
            Path("data.json"),
            "application/json",
        )
    )
    return sorted(targets, key=lambda target: str(target.destination))


def clean_output(output_dir: Path, settings: SiteSettings) -> None:
    """
    Recreate a site output directory after checking its repository boundary.
    """
    output = output_dir.resolve()
    protected = {
        Path("/").resolve(),
        settings.repo_root.resolve(),
        settings.publish_dir.resolve(),
        settings.dataset_dir.resolve(),
    }
    if output in protected or settings.repo_root.resolve() not in output.parents:
        raise ValueError(f"Refusing to clean unsafe site output directory: {output}")
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)


def copy_tree(source: Path, destination: Path) -> int:
    """
    Copy a directory tree and return the number of destination files.
    """
    if not source.exists():
        return 0
    shutil.copytree(source, destination, dirs_exist_ok=True)
    return sum(1 for path in destination.rglob("*") if path.is_file())


def build_site(
    app: Flask,
    output_dir: Path | None = None,
    *,
    check_links: bool = True,
) -> BuildReport:
    """
    Freeze a configured dataset application into static files.
    """
    settings: SiteSettings = app.config["SITE_SETTINGS"]
    catalogue: SiteCatalogue = app.extensions["dataset_catalogue"]
    output = (output_dir or settings.output_dir).resolve()
    clean_output(output, settings)

    client = app.test_client()
    targets = build_targets(catalogue, settings)
    for target in targets:
        response = client.get(target.url)
        if response.status_code != 200:
            raise ValueError(
                f"Could not render {target.url}: HTTP {response.status_code}"
            )
        if not response.content_type.startswith(target.mimetype):
            raise ValueError(
                f"Unexpected content type for {target.url}: {response.content_type}"
            )
        destination = output / target.destination
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(response.data)

    static_folder = Path(str(app.static_folder))
    asset_count = copy_tree(static_folder, output / "assets")
    data_file_count = copy_tree(
        settings.publish_dir / "data",
        output / "data",
    )

    for page in catalogue.analyses.values():
        resource_dir = page.bundle_dir / "notebook_resources"
        asset_count += copy_tree(
            resource_dir,
            output / "analysis" / page.slug / "notebook_resources",
        )

    (output / ".nojekyll").write_text("")
    if check_links:
        check_site_links(output, settings)

    DataIndex.model_validate_json((output / "data.json").read_text())

    return BuildReport(
        output_dir=output,
        page_count=len(targets),
        data_file_count=data_file_count,
        asset_count=asset_count,
    )


class LinkCollector(HTMLParser):
    """
    Collect link-bearing attributes from generated HTML.
    """

    def __init__(self) -> None:
        super().__init__()
        self.links: list[str] = []

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        """
        Record internal-link candidates from one opening tag.
        """
        if tag not in {"a", "img", "script", "link"}:
            return
        attribute = "href" if tag in {"a", "link"} else "src"
        for key, value in attrs:
            if key == attribute and value:
                self.links.append(value)


def link_destination(
    link: str,
    output_dir: Path,
    source_file: Path,
    settings: SiteSettings,
) -> Path | None:
    """
    Resolve a generated HTML link to its expected local destination.
    """
    parsed = urlsplit(link)
    if parsed.scheme or parsed.netloc or not parsed.path:
        return None
    path = parsed.path
    base = settings.base_url.rstrip("/")
    rooted = path.startswith("/")
    if rooted and base:
        if path.startswith(base + "/"):
            path = path[len(base) :]
        elif path == base:
            path = "/"
        else:
            return None

    relative = path.lstrip("/")
    if not relative:
        return output_dir / "index.html"
    destination = (output_dir if rooted else source_file.parent) / relative
    if destination.exists():
        return destination
    if destination.suffix:
        return destination
    html_destination = destination.with_suffix(".html")
    if html_destination.exists():
        return html_destination
    return destination / "index.html"


def check_site_links(output_dir: Path, settings: SiteSettings) -> None:
    """
    Raise an error when generated HTML contains missing internal links.
    """
    missing: list[MissingLink] = []
    for html_file in output_dir.rglob("*.html"):
        parser = LinkCollector()
        parser.feed(html_file.read_text(errors="replace"))
        for link in parser.links:
            if link.startswith(("#", "mailto:", "javascript:")):
                continue
            destination = link_destination(link, output_dir, html_file, settings)
            if destination is not None and not destination.exists():
                missing.append(
                    MissingLink(
                        page=html_file.relative_to(output_dir),
                        link=link,
                    )
                )
    if missing:
        details = "\n".join(
            f"{missing_link.page}: {missing_link.link}" for missing_link in missing[:25]
        )
        raise ValueError(f"Generated site has missing internal links:\n{details}")


def check_site(app: Flask) -> BuildReport:
    """
    Build a temporary copy of the site and validate all internal links.
    """
    settings: SiteSettings = app.config["SITE_SETTINGS"]
    with TemporaryDirectory(prefix="dataset-site-", dir=settings.repo_root) as temp_dir:
        return build_site(app, Path(temp_dir), check_links=True)


def build_from_repo(
    repo_root: Path | None = None,
    output_dir: Path | None = None,
) -> BuildReport:
    """
    Load a repository application and freeze it into static files.
    """
    from . import create_app

    settings = get_site_settings(repo_root=repo_root)
    return build_site(create_app(settings=settings), output_dir)
