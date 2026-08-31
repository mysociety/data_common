from __future__ import annotations

from pathlib import Path
from urllib.parse import urlsplit

import toml
from pydantic import BaseModel, ConfigDict, Field

from ..settings import find_repo_root


class NavigationItem(BaseModel):
    """
    Describe one configured navigation link.
    """

    model_config = ConfigDict(frozen=True)

    title: str
    url: str


class DownloadSettings(BaseModel):
    """
    Configure download forms and optional survey integration.
    """

    model_config = ConfigDict(frozen=True)

    gate: str = "soft"
    survey: str = ""
    form_header: str = "Can you help us by telling us more about yourself?"
    show_code_examples: bool = True
    show_subscription: bool = True


class AnalysisSettings(BaseModel):
    """
    Configure discovery of notebook analysis bundles.
    """

    model_config = ConfigDict(frozen=True)

    enabled: bool = True
    bundle_dir: Path = Path("_render/site/analysis")


class SiteSettings(BaseModel):
    """
    Hold resolved and validated static-site configuration.
    """

    model_config = ConfigDict(frozen=True)

    repo_root: Path
    dataset_dir: Path
    publish_dir: Path
    output_dir: Path
    title: str
    homepage_title: str
    description: str
    intro: str
    base_url: str
    canonical_url: str
    source_url: str
    credit_text: str = ""
    credit_url: str = ""
    accent_colour: str = "#4faded"
    navigation: tuple[NavigationItem, ...] = ()
    downloads: DownloadSettings = Field(default_factory=DownloadSettings)
    analysis: AnalysisSettings = Field(default_factory=AnalysisSettings)

    def public_url(self, path: str = "") -> str:
        """
        Build an absolute public URL below the canonical site URL.
        """
        return self.canonical_url.rstrip("/") + "/" + path.lstrip("/")

    def site_path(self, path: str = "") -> str:
        """
        Build a root-relative path including the configured base URL.
        """
        return (self.base_url.rstrip("/") + "/" + path.lstrip("/")) or "/"


class ProjectConfiguration(BaseModel):
    """
    Represent the project metadata used as site defaults.
    """

    name: str = ""
    description: str = ""


class AnalysisConfiguration(BaseModel):
    """
    Represent unresolved analysis settings read from TOML.
    """

    enabled: bool = True
    bundle_dir: Path = Path("_render/site/analysis")


class SiteConfiguration(BaseModel):
    """
    Represent unresolved site settings read from TOML.
    """

    title: str | None = None
    homepage_title: str | None = None
    description: str | None = None
    intro: str | None = None
    base_url: str | None = None
    canonical_url: str | None = None
    source_url: str | None = None
    output_dir: Path = Path("_site")
    accent_colour: str = "#4faded"
    navigation: list[NavigationItem] = Field(default_factory=list)
    downloads: DownloadSettings = Field(default_factory=DownloadSettings)
    analysis: AnalysisConfiguration = Field(default_factory=AnalysisConfiguration)


class DatasetConfiguration(BaseModel):
    """
    Represent unresolved dataset and site settings read from TOML.
    """

    dataset_dir: Path = Path("data/packages")
    publish_dir: Path = Path("data/packages/_published")
    publish_url: str = ""
    credit_text: str = ""
    credit_url: str = ""
    site: SiteConfiguration = Field(default_factory=SiteConfiguration)


class ToolConfiguration(BaseModel):
    """
    Represent the tool table containing dataset configuration.
    """

    dataset: DatasetConfiguration = Field(default_factory=DatasetConfiguration)


class RepositoryConfiguration(BaseModel):
    """
    Validate the subset of pyproject.toml consumed by the site.
    """

    project: ProjectConfiguration = Field(default_factory=ProjectConfiguration)
    tool: ToolConfiguration = Field(default_factory=ToolConfiguration)


def normalise_base_url(value: str) -> str:
    """
    Convert an optional URL path into the site's canonical base-path form.
    """
    value = value.strip()
    if not value or value == "/":
        return ""
    return "/" + value.strip("/")


def resolve_repo_path(root: Path, value: str | Path) -> Path:
    """
    Resolve a configured path relative to its repository.
    """
    path = Path(value)
    return path if path.is_absolute() else root / path


def get_site_settings(
    toml_file: str | Path = "pyproject.toml",
    *,
    repo_root: Path | None = None,
) -> SiteSettings:
    """
    Load and validate site settings from a repository pyproject.toml.
    """
    root = repo_root.resolve() if repo_root else find_repo_root()
    config_path = Path(toml_file)
    if not config_path.is_absolute():
        config_path = root / config_path

    config = RepositoryConfiguration.model_validate(toml.load(config_path))
    dataset = config.tool.dataset
    site = dataset.site

    publish_url = dataset.publish_url.rstrip("/")
    inferred_canonical = publish_url.removesuffix("/datasets")
    canonical_url = (site.canonical_url or inferred_canonical).rstrip("/")
    parsed = urlsplit(canonical_url)
    inferred_base = parsed.path if parsed.scheme else ""
    base_url = normalise_base_url(site.base_url or inferred_base)

    title = site.title or config.project.name or root.name
    description = site.description or config.project.description

    return SiteSettings(
        repo_root=root,
        dataset_dir=resolve_repo_path(root, dataset.dataset_dir),
        publish_dir=resolve_repo_path(root, dataset.publish_dir),
        output_dir=resolve_repo_path(root, site.output_dir),
        title=title,
        homepage_title=site.homepage_title or title,
        description=description,
        intro=site.intro or description,
        base_url=base_url,
        canonical_url=canonical_url,
        source_url=site.source_url or f"https://github.com/mysociety/{root.name}",
        credit_text=dataset.credit_text,
        credit_url=dataset.credit_url,
        accent_colour=site.accent_colour,
        navigation=tuple(site.navigation),
        downloads=site.downloads,
        analysis=AnalysisSettings(
            enabled=site.analysis.enabled,
            bundle_dir=resolve_repo_path(root, site.analysis.bundle_dir),
        ),
    )
