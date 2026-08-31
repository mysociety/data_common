from __future__ import annotations

from pathlib import Path

from data_common.dataset import DataPackageExtras
from data_common.dataset.resource_management import DataPackage


def test_datapackage_exposes_typed_custom_metadata(
    model_repository: Path,
) -> None:
    """
    Parse build, test, format, and composite settings from custom metadata.
    """
    package = DataPackage(model_repository / "data" / "packages" / "people")

    extras = package.extras

    assert isinstance(extras, DataPackageExtras)
    assert extras.dataset_order == 1
    assert extras.tests == ["test_people"]
    assert extras.formats.csv is True
    assert extras.formats.parquet is False
    assert extras.composite.for_format("json").render is True


def test_extras_defaults_cover_every_resource_management_setting() -> None:
    """
    Supply stable defaults when a datapackage has no custom metadata.
    """
    extras = DataPackageExtras.from_datapackage({})

    assert extras.build == ""
    assert extras.tests == []
    assert extras.dataset_order == 999
    assert extras.is_geodata is False
    assert extras.formats.model_dump() == {
        "csv": True,
        "parquet": True,
        "geojson": False,
        "gpkg": False,
    }
    assert extras.download_options.survey == "default"
    assert extras.change_log == {}


def test_extras_retain_extensions_during_change_log_updates() -> None:
    """
    Preserve unknown repository metadata when writing typed extras back to disk.
    """
    extras = DataPackageExtras.from_datapackage(
        {
            "custom": {
                "formats": {"csv": False, "xml": True},
                "composite": {"xlsx": {"modify": {"alt-names": "split-to-array"}}},
                "repository_extension": {"enabled": True},
            }
        }
    )

    stored = extras.with_change("1.2.3", "Updated data").as_datapackage_value()

    assert stored["formats"] == {"csv": False, "xml": True}
    assert stored["composite"]["xlsx"]["modify"] == {"alt-names": "split-to-array"}
    assert stored["repository_extension"] == {"enabled": True}
    assert stored["change_log"] == {"1.2.3": "Updated data"}


def test_publication_json_uses_typed_dataset_defaults(
    model_repository: Path,
) -> None:
    """
    Add ordering and Datasette defaults without expanding unrelated settings.
    """
    package = DataPackage(model_repository / "data" / "packages" / "places")

    custom = package.get_current_datapackage_json()["custom"]

    assert custom == {
        "dataset_order": 999,
        "datasette": {
            "about": "Info & Downloads",
            "about_url": package.url,
        },
    }
