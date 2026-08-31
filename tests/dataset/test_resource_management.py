from __future__ import annotations

from pathlib import Path

from ruamel.yaml import YAML

from data_common.dataset.resource_management import (
    CompositeOptions,
    DataPackage,
    ValidationErrorItem,
)


def test_composite_options_are_resolved_to_a_typed_model(
    model_repository: Path,
) -> None:
    """
    Resolve all-resource defaults before composite builders consume them.
    """
    package = DataPackage(model_repository / "data" / "packages" / "people")

    options = package.get_composite_options("xlsx")

    assert isinstance(options, CompositeOptions)
    assert options.include == ["people"]
    assert options.exclude == []
    assert options.render is True


def test_package_validation_returns_named_error_records(
    model_repository: Path,
) -> None:
    """
    Return validation failures as named records rather than bare tuples.
    """
    package_path = model_repository / "data" / "packages" / "places"
    datapackage = package_path / "datapackage.yaml"
    datapackage.write_text(
        datapackage.read_text().replace(
            "description: A minimal dataset used to test defaults.\n", ""
        )
    )
    package = DataPackage(package_path)

    errors = package.validate(quiet=True)

    assert errors
    assert all(isinstance(error, ValidationErrorItem) for error in errors)


def test_rebuilding_unchanged_resource_preserves_derived_schema(
    model_repository: Path,
) -> None:
    """
    Preserve schema metadata when the resource content hash has not changed.
    """
    package = DataPackage(model_repository / "data" / "packages" / "people")
    package.rebuild_all_resources()
    resource_path = package.path / "people.resource.yaml"
    yaml = YAML()
    with resource_path.open() as stream:
        resource = yaml.load(stream)
    resource["schema"]["fields"][0]["example"] = "legacy example"
    with resource_path.open("w") as stream:
        yaml.dump(resource, stream)

    package.rebuild_all_resources()

    with resource_path.open() as stream:
        rebuilt_resource = YAML(typ="safe").load(stream)
    assert rebuilt_resource["schema"]["fields"][0]["example"] == "legacy example"


def test_legacy_row_count_does_not_bump_unchanged_data(
    model_repository: Path,
) -> None:
    """
    Ignore a legacy header-inclusive row count when the data hash is unchanged.
    """
    package = DataPackage(model_repository / "data" / "packages" / "people")
    package.rebuild_all_resources()
    package.store_version()

    stored_resource_path = package.path / "versions" / "1.0.0" / "people.resource.yaml"
    yaml = YAML()
    stored_resource = yaml.load(stored_resource_path)
    stored_resource["custom"]["row_count"] += 1
    with stored_resource_path.open("w") as stream:
        yaml.dump(stored_resource, stream)

    assert package.derive_bump_rule_from_change() is None


def test_changed_row_count_remains_a_minor_change(
    model_repository: Path,
) -> None:
    """
    Treat a genuine change in the number of data rows as a minor change.
    """
    package = DataPackage(model_repository / "data" / "packages" / "people")
    package.rebuild_all_resources()
    package.store_version()
    with (package.path / "people.csv").open("a") as stream:
        stream.write("4,Katherine,true\n")
    package.rebuild_all_resources()

    assert package.derive_bump_rule_from_change() == (
        "MINOR",
        "Change in data for resource(s): people",
    )
