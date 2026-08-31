from __future__ import annotations

from pathlib import Path

from data_common.dataset.resource_management import DataPackage


def test_dataset_owned_pytest_file_passes(model_repository: Path) -> None:
    package = DataPackage(model_repository / "data/packages/people")

    assert package.test_package() is True


def test_failing_dataset_owned_pytest_file_fails_package(
    model_repository: Path,
) -> None:
    consumer_test = model_repository / "tests/test_people.py"
    consumer_test.write_text(
        "def test_dataset_contract():\n"
        "    assert False, 'consumer dataset check failed'\n"
    )
    package = DataPackage(model_repository / "data/packages/people")

    assert package.test_package() is False


def test_missing_configured_dataset_test_fails_package(
    model_repository: Path,
) -> None:
    datapackage = model_repository / "data/packages/people/datapackage.yaml"
    contents = datapackage.read_text().replace(
        "    - test_people",
        "    - test_does_not_exist",
    )
    datapackage.write_text(contents)
