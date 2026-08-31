from __future__ import annotations

from pathlib import Path

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
