from __future__ import annotations

import sys
from collections.abc import Callable
from pathlib import Path
from types import ModuleType

import pytest
from click.testing import CliRunner
from flask import Blueprint, Flask, render_template_string

from data_common.dataset.__main__ import cli
from data_common.dataset.site import create_app
from data_common.dataset.site.extensions import SiteExtension
from data_common.dataset.site.freezer import build_site, check_site_links
from data_common.dataset.site.models import BuildTarget
from data_common.dataset.site.settings import SiteSettings, get_site_settings


def test_scaffold_can_be_registered_served_and_frozen(
    model_repository: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    Exercise generated Python, config loading, shared templates and static output.
    """
    runner = CliRunner()
    args = [
        "create-extension",
        "--module",
        "example_extension",
        "--title",
        "Example <page>",
        "--route",
        "example",
        "--repo-root",
        str(model_repository),
    ]
    result = runner.invoke(cli, args)
    assert result.exit_code == 0, result.output
    assert "example_extension:create_extension" in result.output
    assert runner.invoke(cli, args).exit_code != 0
    monkeypatch.syspath_prepend(str(model_repository / "src"))
    config = model_repository / "pyproject.toml"
    config.write_text(
        config.read_text().replace(
            "[tool.dataset.site]",
            '[tool.dataset.site]\nextensions = ["example_extension:create_extension"]',
        )
    )
    try:
        app = create_app(repo_root=model_repository)
        page = app.test_client().get("/model/example/")
        assert page.status_code == 200
        assert b"Example &lt;page&gt;" in page.data
        assert b"mysoc-footer" in page.data
        report = build_site(app)
        assert (report.output_dir / "example/index.html").exists()
        assert b"/model/example/" in (report.output_dir / "index.html").read_bytes()
    finally:
        sys.modules.pop("example_extension", None)


@pytest.mark.parametrize(
    "module,route",
    [
        ("../escape", "page"),
        ("example", "../escape"),
        ("example", "data/page"),
        ("class", "page"),
    ],
)
def test_scaffold_rejects_invalid_parameters(
    tmp_path: Path, module: str, route: str
) -> None:
    """
    Reject invalid module names and reserved or escaping routes before writing.
    """
    result = CliRunner().invoke(
        cli,
        [
            "create-extension",
            "--module",
            module,
            "--title",
            "Title",
            "--route",
            route,
            "--repo-root",
            str(tmp_path),
        ],
    )
    assert result.exit_code != 0
    assert not (tmp_path / "src").exists()


@pytest.mark.parametrize(
    "destination",
    [
        "../outside.html",
        "/outside.html",
        "index.html",
        "assets/site.css",
        "data/thing.json",
        ".nojekyll",
        ".nojekyll/child.html",
        "analysis/coverage/notebook_resources/chart.svg",
        "analysis/coverage/notebook_resources/chart.svg/child.html",
        "analysis/coverage/notebook_resources",
        "analysis/coverage",
        "analysis",
    ],
)
def test_extension_targets_reject_collisions_and_unsafe_paths(
    model_repository: Path, destination: str
) -> None:
    """
    Validate extension output before the existing build directory is cleaned.
    """
    settings = get_site_settings(repo_root=model_repository)
    app = create_app(settings=settings)
    extension = SiteExtension(
        Blueprint("bad", __name__), [BuildTarget("/model/extra/", Path(destination))]
    )
    app.extensions["dataset_site_extensions"] = [extension]
    settings.output_dir.mkdir()
    previous_build = settings.output_dir / "previous.html"
    previous_build.write_text("Keep this build")
    with pytest.raises(ValueError):
        build_site(app)
    assert previous_build.read_text() == "Keep this build"


def extension_app(
    repository: Path,
    monkeypatch: pytest.MonkeyPatch,
    factory: Callable[[SiteSettings], SiteExtension],
    base_url: str = "/model",
) -> Flask:
    """
    Load a test factory through the same configuration path as a project module.
    """
    module = ModuleType("test_site_extension")
    monkeypatch.setattr(module, "create_extension", factory, raising=False)
    monkeypatch.setitem(sys.modules, module.__name__, module)
    settings = get_site_settings(repo_root=repository).model_copy(
        update={
            "extensions": (f"{module.__name__}:create_extension",),
            "base_url": base_url,
        }
    )
    return create_app(settings=settings)


@pytest.mark.parametrize("base_url", ["", "/model"])
def test_blueprint_prefix_is_preserved(
    model_repository: Path, monkeypatch: pytest.MonkeyPatch, base_url: str
) -> None:
    """
    Compose blueprint and site prefixes when serving and freezing pages.
    """

    def factory(settings: SiteSettings) -> SiteExtension:
        blueprint = Blueprint("prefixed", __name__, url_prefix="/extra")
        blueprint.add_url_rule("/hello/", view_func=lambda: "Hello")
        return SiteExtension(
            blueprint,
            [
                BuildTarget(
                    settings.site_path("extra/hello/"), Path("extra/hello/index.html")
                )
            ],
        )

    app = extension_app(model_repository, monkeypatch, factory, base_url)
    assert app.test_client().get(f"{base_url}/extra/hello/").data == b"Hello"
    assert app.test_client().get(f"{base_url}/hello/").status_code == 404
    report = build_site(app)
    assert (report.output_dir / "extra/hello/index.html").read_text() == "Hello"


@pytest.mark.parametrize("base_url", ["", "/model"])
@pytest.mark.parametrize(
    "filename",
    ["hello world.txt", "café.txt", "50%.txt", "literal%20.txt", "hash#.txt"],
)
def test_static_assets_preserve_filenames_and_factory_targets(
    model_repository: Path,
    monkeypatch: pytest.MonkeyPatch,
    base_url: str,
    filename: str,
) -> None:
    """
    Freeze escaped asset URLs without encoding filenames or mutating factories.
    """
    folder = model_repository / "extension_assets"
    folder.mkdir()
    (folder / filename).write_text("Asset content")
    blueprint = Blueprint(
        "extension_assets",
        __name__,
        url_prefix="/extra",
        static_folder=str(folder),
        static_url_path="/assets",
    )

    @blueprint.get("/")
    def index() -> str:
        """
        Render the asset URL as extension authors would in a template.
        """
        return render_template_string(
            '<a href="{{ url_for("extension_assets.static", filename=filename) }}">Asset</a>',
            filename=filename,
        )

    extension = SiteExtension(
        blueprint,
        [BuildTarget(f"{base_url}/extra/", Path("extra/index.html"))],
    )

    def factory(settings: SiteSettings) -> SiteExtension:
        """
        Reuse an extension declaration across multiple application instances.
        """
        return extension

    for _ in range(2):
        app = extension_app(model_repository, monkeypatch, factory, base_url)
        report = build_site(app)
        assert (
            report.output_dir / "extra/assets" / filename
        ).read_text() == "Asset content"
        assert len(extension.targets) == 1

    (report.output_dir / "extra/assets" / filename).unlink()
    with pytest.raises(ValueError, match="missing internal links"):
        check_site_links(report.output_dir, app.config["SITE_SETTINGS"])


def test_separate_get_and_post_routes_are_allowed(
    model_repository: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    Ignore automatic OPTIONS when comparing otherwise disjoint HTTP methods.
    """

    def factory(settings: SiteSettings) -> SiteExtension:
        blueprint = Blueprint("methods", __name__)
        blueprint.add_url_rule("/extra/", "read", lambda: "Read", methods=["GET"])
        blueprint.add_url_rule("/extra/", "write", lambda: "Write", methods=["POST"])
        return SiteExtension(blueprint)

    app = extension_app(model_repository, monkeypatch, factory)
    assert app.test_client().get("/model/extra/").data == b"Read"
    assert app.test_client().post("/model/extra/").data == b"Write"


@pytest.mark.parametrize(
    "route",
    [
        "/datasets/<package>/<version>",
        "/datasets/<name>/<release>",
        "/datasets/<string:name>/<string:release>",
    ],
)
def test_equivalent_core_routes_are_rejected(
    model_repository: Path, monkeypatch: pytest.MonkeyPatch, route: str
) -> None:
    """
    Reject shadowing core routes even when argument names or spellings differ.
    """

    def factory(settings: SiteSettings) -> SiteExtension:
        blueprint = Blueprint("conflict", __name__)
        blueprint.add_url_rule(route, view_func=lambda **kwargs: "Shadowed")
        return SiteExtension(blueprint)

    with pytest.raises(ValueError, match="Conflicting route"):
        extension_app(model_repository, monkeypatch, factory)


def test_equivalent_routes_within_extension_are_rejected(
    model_repository: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    Check new routes against each other as well as existing application routes.
    """

    def factory(settings: SiteSettings) -> SiteExtension:
        blueprint = Blueprint("conflict", __name__)
        blueprint.add_url_rule("/extra/<id>/", "first", lambda **kwargs: "First")
        blueprint.add_url_rule("/extra/<name>/", "second", lambda **kwargs: "Second")
        return SiteExtension(blueprint)

    with pytest.raises(ValueError, match="Conflicting route"):
        extension_app(model_repository, monkeypatch, factory)


@pytest.mark.parametrize("mimetype", [None, "application/json"])
def test_response_mime_validation_is_explicit(
    model_repository: Path, monkeypatch: pytest.MonkeyPatch, mimetype: str | None
) -> None:
    """
    Skip MIME checks only when requested and reject declared type mismatches.
    """

    def factory(settings: SiteSettings) -> SiteExtension:
        blueprint = Blueprint("mime", __name__)
        blueprint.add_url_rule("/extra/", view_func=lambda: "HTML response")
        return SiteExtension(
            blueprint,
            [
                BuildTarget(
                    settings.site_path("extra/"), Path("extra/index.html"), mimetype
                )
            ],
        )

    app = extension_app(model_repository, monkeypatch, factory)
    if mimetype is None:
        report = build_site(app)
        assert (report.output_dir / "extra/index.html").read_text() == "HTML response"
    else:
        with pytest.raises(ValueError, match="Unexpected content type"):
            build_site(app)
