from __future__ import annotations

import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field, replace
from importlib import import_module
from pathlib import Path
from typing import NamedTuple, cast
from urllib.parse import unquote, urlsplit

from flask import Blueprint, Flask, url_for
from werkzeug.routing import Rule

from .models import BuildTarget
from .settings import NavigationItem, SiteSettings


@dataclass
class SiteExtension:
    """
    Register a blueprint, explicit static pages and shared navigation.

    Factories receive resolved SiteSettings. Target URLs include base_url;
    destinations are relative to the build directory. Blueprint static files
    are discovered automatically and frozen alongside the declared pages.
    Navigation entries appear in the header and the homepage Tools list.
    """

    blueprint: Blueprint
    targets: list[BuildTarget] = field(default_factory=list)
    navigation: list[NavigationItem] = field(default_factory=list)


class RouteShape(NamedTuple):
    """
    Identify equivalent routing patterns without their parameter names.
    """

    path: str
    host: str | None
    subdomain: str | None
    websocket: bool


def load_extension(reference: str, settings: SiteSettings) -> SiteExtension:
    """
    Import a configured factory and check its extension contract.
    """
    module, separator, name = reference.partition(":")
    if not separator or not module or not name:
        raise ValueError(f"Expected extension reference module:factory: {reference}")
    factory = getattr(import_module(module), name)
    if not callable(factory):
        raise TypeError(f"{reference} must be a callable extension factory")
    extension = cast(Callable[[SiteSettings], SiteExtension], factory)(settings)
    if not isinstance(extension, SiteExtension):
        raise TypeError(f"{reference} must return a SiteExtension")
    return extension


def route_shape(rule: Rule) -> RouteShape:
    """
    Preserve converters while ignoring argument names and implicit string types.
    """
    path = re.sub(
        r"<(?:(?P<converter>[^<>]+):)?[a-zA-Z_]\w*>",
        lambda match: f"<{match.group('converter') or 'string'}>",
        rule.rule,
    )
    return RouteShape(path, rule.host, rule.subdomain, rule.websocket)


def validate_extension_routes(
    existing_routes: Iterable[Rule],
    new_routes: Iterable[Rule],
    reference: str,
) -> None:
    """
    Reject equivalent patterns with overlapping methods, ignoring OPTIONS.

    Different parameter names do not distinguish routes. Different converters
    and static versus variable routes retain Flask's normal matching precedence;
    this check does not attempt to detect all overlapping URL patterns.
    """
    methods_by_route: dict[RouteShape, set[str]] = {}
    for rule in existing_routes:
        methods_by_route.setdefault(route_shape(rule), set()).update(
            (rule.methods or set()) - {"OPTIONS"}
        )
    for rule in new_routes:
        methods = (rule.methods or set()) - {"OPTIONS"}
        existing_methods = methods_by_route.setdefault(route_shape(rule), set())
        if existing_methods.intersection(methods):
            raise ValueError(f"Conflicting route in extension {reference}: {rule.rule}")
        existing_methods.update(methods)


def discover_static_targets(
    app: Flask, blueprint: Blueprint, settings: SiteSettings
) -> list[BuildTarget]:
    """
    Map blueprint assets from encoded request URLs to decoded output paths.
    """
    if not blueprint.static_folder:
        return []
    folder = Path(blueprint.static_folder)
    targets: list[BuildTarget] = []
    with app.test_request_context():
        for path in sorted(folder.rglob("*")):
            if path.is_file():
                url = url_for(
                    f"{blueprint.name}.static",
                    filename=path.relative_to(folder).as_posix(),
                )
                relative_url = urlsplit(url).path.removeprefix(settings.base_url)
                destination = Path(unquote(relative_url).lstrip("/"))
                targets.append(BuildTarget(url, destination, mimetype=None))
    return targets


def register_extensions(app: Flask, settings: SiteSettings) -> None:
    """
    Register configured extensions without changing factory-owned target lists.
    """
    extensions: list[SiteExtension] = []
    for reference in settings.extensions:
        extension = load_extension(reference, settings)
        blueprint = extension.blueprint
        existing_routes = list(app.url_map.iter_rules())
        prefix = settings.base_url + (blueprint.url_prefix or "")
        app.register_blueprint(blueprint, url_prefix=prefix)
        new_routes = [
            rule
            for rule in app.url_map.iter_rules()
            if rule.endpoint.startswith(blueprint.name + ".")
        ]
        validate_extension_routes(existing_routes, new_routes, reference)
        extensions.append(
            replace(
                extension,
                targets=[
                    *extension.targets,
                    *discover_static_targets(app, blueprint, settings),
                ],
            )
        )
    app.extensions["dataset_site_extensions"] = extensions
    app.extensions["dataset_navigation"] = [
        *settings.navigation,
        *(item for extension in extensions for item in extension.navigation),
    ]
