from __future__ import annotations

from pathlib import Path
from typing import Any

from flask import Flask
from markdown_it import MarkdownIt
from markupsafe import Markup

from .catalogue import SiteCatalogue
from .settings import SiteSettings, get_site_settings
from .views import site


def create_app(
    repo_root: Path | None = None,
    test_config: dict[str, Any] | None = None,
    *,
    settings: SiteSettings | None = None,
) -> Flask:
    """
    Create a dataset site application for one repository.
    """
    site_settings = settings or get_site_settings(repo_root=repo_root)
    static_url_path = f"{site_settings.base_url}/assets"
    app = Flask(
        __name__,
        template_folder="templates",
        static_folder="static",
        static_url_path=static_url_path,
    )
    app.config.from_mapping(
        SITE_SETTINGS=site_settings,
        FREEZE_MODE=False,
    )
    if test_config:
        app.config.update(test_config)

    catalogue = SiteCatalogue(site_settings)
    app.extensions["dataset_catalogue"] = catalogue

    markdown = MarkdownIt("commonmark", {"html": False})

    @app.template_filter("markdown")
    def markdown_filter(value: object) -> Markup:
        """
        Render block Markdown without permitting embedded HTML.
        """
        return Markup(markdown.render(str(value or "")))

    @app.template_filter("markdown_inline")
    def markdown_inline_filter(value: object) -> Markup:
        """
        Render inline Markdown without permitting embedded HTML.
        """
        return Markup(markdown.renderInline(str(value or "")))

    @app.template_filter("route_version")
    def route_version_filter(value: object) -> str:
        """
        Convert a version label to its URL route representation.
        """
        return str(value).replace(".", "_")

    @app.context_processor
    def site_context() -> dict[str, Any]:
        """
        Expose typed site configuration and path generation to templates.
        """
        return {
            "site_settings": site_settings,
            "site_path": site_settings.site_path,
        }

    app.register_blueprint(site, url_prefix=site_settings.base_url)
    return app


__all__ = ["SiteCatalogue", "SiteSettings", "create_app", "get_site_settings"]
